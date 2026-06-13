from pathlib import Path
import json
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_timeline.video_clipper import VideoClipperError, clip_timeline_entry


class VideoClipperTest(unittest.TestCase):
    def test_clip_timeline_entry_runs_ffmpeg_for_selected_timeline_range(self):
        document = {
            "video": {"path": "/tmp/source.mp4"},
            "timeline": [
                {"start_seconds": 5.0, "end_seconds": 10.0},
                {"start_seconds": 20.0, "end_seconds": 35.0},
            ],
        }

        with TemporaryDirectory() as directory:
            timeline_path = Path(directory) / "timeline.json"
            output_path = Path(directory) / "clip.mp4"
            timeline_path.write_text(json.dumps(document), encoding="utf-8")

            with patch("video_timeline.video_clipper.subprocess.run") as run:
                result = clip_timeline_entry(timeline_path, index=1, output_path=output_path, padding_seconds=2.5)

        self.assertEqual(result, output_path)
        run.assert_called_once()
        command = run.call_args.args[0]
        self.assertEqual(
            command,
            [
                "ffmpeg",
                "-y",
                "-ss",
                "17.5",
                "-i",
                "/tmp/source.mp4",
                "-t",
                "20",
                "-c",
                "copy",
                str(output_path),
            ],
        )

    def test_clip_timeline_entry_can_use_accurate_reencode_mode(self):
        document = {
            "video": {"path": "/tmp/source.mp4"},
            "timeline": [{"start_seconds": 20.0, "end_seconds": 35.0}],
        }

        with TemporaryDirectory() as directory:
            timeline_path = Path(directory) / "timeline.json"
            output_path = Path(directory) / "clip.mp4"
            timeline_path.write_text(json.dumps(document), encoding="utf-8")

            with patch("video_timeline.video_clipper.subprocess.run") as run:
                clip_timeline_entry(timeline_path, index=0, output_path=output_path, padding_seconds=2.5, accurate=True)

        command = run.call_args.args[0]
        self.assertEqual(
            command,
            [
                "ffmpeg",
                "-y",
                "-i",
                "/tmp/source.mp4",
                "-ss",
                "17.5",
                "-t",
                "20",
                "-c:v",
                "libx264",
                "-crf",
                "18",
                "-preset",
                "veryfast",
                "-c:a",
                "aac",
                str(output_path),
            ],
        )

    def test_clip_timeline_entry_can_customize_accurate_reencode_quality_and_speed(self):
        document = {
            "video": {"path": "/tmp/source.mp4"},
            "timeline": [{"start_seconds": 20.0, "end_seconds": 35.0}],
        }

        with TemporaryDirectory() as directory:
            timeline_path = Path(directory) / "timeline.json"
            output_path = Path(directory) / "clip.mp4"
            timeline_path.write_text(json.dumps(document), encoding="utf-8")

            with patch("video_timeline.video_clipper.subprocess.run") as run:
                clip_timeline_entry(
                    timeline_path,
                    index=0,
                    output_path=output_path,
                    accurate=True,
                    crf=20,
                    preset="fast",
                )

        command = run.call_args.args[0]
        self.assertIn("-crf", command)
        self.assertIn("20", command)
        self.assertIn("-preset", command)
        self.assertIn("fast", command)

    def test_clip_timeline_entry_rejects_reencode_options_without_accurate_mode(self):
        document = {
            "video": {"path": "/tmp/source.mp4"},
            "timeline": [{"start_seconds": 20.0, "end_seconds": 35.0}],
        }

        with TemporaryDirectory() as directory:
            timeline_path = Path(directory) / "timeline.json"
            timeline_path.write_text(json.dumps(document), encoding="utf-8")

            with self.assertRaisesRegex(VideoClipperError, "--accurate"):
                clip_timeline_entry(timeline_path, index=0, output_path=Path(directory) / "clip.mp4", crf=18)

    def test_clip_timeline_entry_rejects_invalid_reencode_options(self):
        document = {
            "video": {"path": "/tmp/source.mp4"},
            "timeline": [{"start_seconds": 20.0, "end_seconds": 35.0}],
        }

        with TemporaryDirectory() as directory:
            timeline_path = Path(directory) / "timeline.json"
            timeline_path.write_text(json.dumps(document), encoding="utf-8")

            with self.assertRaisesRegex(VideoClipperError, "--crf"):
                clip_timeline_entry(
                    timeline_path,
                    index=0,
                    output_path=Path(directory) / "clip.mp4",
                    accurate=True,
                    crf=52,
                )
            with self.assertRaisesRegex(VideoClipperError, "--preset"):
                clip_timeline_entry(
                    timeline_path,
                    index=0,
                    output_path=Path(directory) / "clip.mp4",
                    accurate=True,
                    preset="quick",
                )

    def test_clip_timeline_entry_clamps_padding_start_to_zero(self):
        document = {
            "video": {"path": "/tmp/source.mp4"},
            "timeline": [{"start_seconds": 1.0, "end_seconds": 4.0}],
        }

        with TemporaryDirectory() as directory:
            timeline_path = Path(directory) / "timeline.json"
            output_path = Path(directory) / "clip.mp4"
            timeline_path.write_text(json.dumps(document), encoding="utf-8")

            with patch("video_timeline.video_clipper.subprocess.run") as run:
                clip_timeline_entry(timeline_path, index=0, output_path=output_path, padding_seconds=3.0)

        command = run.call_args.args[0]
        self.assertEqual(command[3], "0")
        self.assertEqual(command[7], "7")

    def test_clip_timeline_entry_rejects_missing_index(self):
        document = {
            "video": {"path": "/tmp/source.mp4"},
            "timeline": [{"start_seconds": 1.0, "end_seconds": 4.0}],
        }

        with TemporaryDirectory() as directory:
            timeline_path = Path(directory) / "timeline.json"
            timeline_path.write_text(json.dumps(document), encoding="utf-8")

            with self.assertRaisesRegex(VideoClipperError, "timeline index"):
                clip_timeline_entry(timeline_path, index=2, output_path=Path(directory) / "clip.mp4")

    def test_clip_timeline_entry_rejects_invalid_range(self):
        document = {
            "video": {"path": "/tmp/source.mp4"},
            "timeline": [{"start_seconds": 4.0, "end_seconds": 4.0}],
        }

        with TemporaryDirectory() as directory:
            timeline_path = Path(directory) / "timeline.json"
            timeline_path.write_text(json.dumps(document), encoding="utf-8")

            with self.assertRaisesRegex(VideoClipperError, "範囲"):
                clip_timeline_entry(timeline_path, index=0, output_path=Path(directory) / "clip.mp4")


if __name__ == "__main__":
    unittest.main()
