from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_timeline.video_loader import VideoLoaderError, load_video_metadata


class VideoLoaderTest(unittest.TestCase):
    def test_load_video_metadata_from_ffprobe_json(self):
        with TemporaryDirectory() as directory:
            video_path = Path(directory) / "input.mp4"
            video_path.write_bytes(b"fake")

            with patch("video_timeline.video_loader.subprocess.run") as run:
                run.return_value.stdout = """{
                  "format": {"duration": "12.5"},
                  "streams": [
                    {
                      "codec_type": "video",
                      "duration": "12.5",
                      "avg_frame_rate": "30000/1001",
                      "nb_frames": "375",
                      "width": 1920,
                      "height": 1080
                    }
                  ]
                }"""

                metadata = load_video_metadata(video_path)

        self.assertEqual(metadata.path, str(video_path))
        self.assertEqual(metadata.duration_seconds, 12.5)
        self.assertAlmostEqual(metadata.fps, 29.97002997)
        self.assertEqual(metadata.frame_count, 375)
        self.assertEqual(metadata.width, 1920)
        self.assertEqual(metadata.height, 1080)
        self.assertEqual(
            metadata.to_dict(),
            {
                "path": str(video_path),
                "duration_seconds": 12.5,
                "fps": metadata.fps,
                "frame_count": 375,
                "width": 1920,
                "height": 1080,
            },
        )

    def test_missing_file_raises_clear_error(self):
        with self.assertRaisesRegex(VideoLoaderError, "存在しません"):
            load_video_metadata("missing.mp4")

    def test_unsupported_extension_raises_clear_error(self):
        with TemporaryDirectory() as directory:
            video_path = Path(directory) / "input.mov"
            video_path.write_bytes(b"fake")

            with self.assertRaisesRegex(VideoLoaderError, "未対応"):
                load_video_metadata(video_path)

    def test_ffprobe_failure_raises_clear_error(self):
        with TemporaryDirectory() as directory:
            video_path = Path(directory) / "input.mp4"
            video_path.write_bytes(b"fake")

            with patch("video_timeline.video_loader.subprocess.run") as run:
                run.side_effect = subprocess.CalledProcessError(
                    returncode=1,
                    cmd=["ffprobe"],
                    stderr="invalid data",
                )

                with self.assertRaisesRegex(VideoLoaderError, "動画メタデータを取得できません"):
                    load_video_metadata(video_path)

    def test_missing_frame_count_falls_back_to_duration_and_fps(self):
        with TemporaryDirectory() as directory:
            video_path = Path(directory) / "input.mp4"
            video_path.write_bytes(b"fake")

            with patch("video_timeline.video_loader.subprocess.run") as run:
                run.return_value.stdout = """{
                  "format": {"duration": "2.0"},
                  "streams": [
                    {
                      "codec_type": "video",
                      "avg_frame_rate": "30/1",
                      "width": 320,
                      "height": 180
                    }
                  ]
                }"""

                metadata = load_video_metadata(video_path)

        self.assertEqual(metadata.frame_count, 60)


if __name__ == "__main__":
    unittest.main()
