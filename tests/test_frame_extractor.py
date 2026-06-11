from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_timeline.frame_extractor import (
    FrameExtractorError,
    extract_frames,
    format_frame_filename,
    generate_frame_times,
)
from video_timeline.video_loader import VideoMetadata


class FrameExtractorTest(unittest.TestCase):
    def test_generate_frame_times_starts_at_zero_and_excludes_duration(self):
        self.assertEqual(generate_frame_times(25.0, 10.0), [0.0, 10.0, 20.0])

    def test_generate_frame_times_returns_zero_for_short_video(self):
        self.assertEqual(generate_frame_times(3.0, 10.0), [0.0])

    def test_generate_frame_times_rejects_invalid_values(self):
        with self.assertRaisesRegex(FrameExtractorError, "duration_seconds"):
            generate_frame_times(0.0, 10.0)
        with self.assertRaisesRegex(FrameExtractorError, "interval_seconds"):
            generate_frame_times(10.0, 0.0)

    def test_format_frame_filename_uses_seconds(self):
        self.assertEqual(format_frame_filename(0.0), "000000.jpg")
        self.assertEqual(format_frame_filename(10.0), "000010.jpg")
        self.assertEqual(format_frame_filename(120.4), "000120.jpg")

    def test_extract_frames_runs_ffmpeg_for_each_time(self):
        metadata = VideoMetadata(
            path="/tmp/input.mp4",
            duration_seconds=21.0,
            fps=30.0,
            frame_count=630,
            width=1920,
            height=1080,
        )

        with TemporaryDirectory() as directory:
            frames_dir = Path(directory) / "frames"
            with patch("video_timeline.frame_extractor.subprocess.run") as run:
                frames = extract_frames(metadata, frames_dir=frames_dir, interval_seconds=10.0)

        self.assertEqual([frame.time_seconds for frame in frames], [0.0, 10.0, 20.0])
        self.assertEqual([frame.index for frame in frames], [0, 1, 2])
        self.assertEqual([Path(frame.image).name for frame in frames], ["000000.jpg", "000010.jpg", "000020.jpg"])
        self.assertEqual(run.call_count, 3)
        first_command = run.call_args_list[0].args[0]
        self.assertEqual(first_command[:2], ["ffmpeg", "-y"])
        self.assertIn("/tmp/input.mp4", first_command)
        self.assertIn("0.000000", first_command)

    def test_extract_frames_rejects_invalid_interval(self):
        metadata = VideoMetadata(
            path="/tmp/input.mp4",
            duration_seconds=1.0,
            fps=30.0,
            frame_count=30,
            width=320,
            height=180,
        )

        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FrameExtractorError, "interval_seconds"):
                extract_frames(metadata, frames_dir=directory, interval_seconds=0.0)

    def test_extract_frames_wraps_ffmpeg_failure(self):
        metadata = VideoMetadata(
            path="/tmp/input.mp4",
            duration_seconds=1.0,
            fps=30.0,
            frame_count=30,
            width=320,
            height=180,
        )

        with TemporaryDirectory() as directory:
            with patch("video_timeline.frame_extractor.subprocess.run") as run:
                run.side_effect = subprocess.CalledProcessError(
                    returncode=1,
                    cmd=["ffmpeg"],
                    stderr="invalid data",
                )

                with self.assertRaisesRegex(FrameExtractorError, "フレームを抽出できません"):
                    extract_frames(metadata, frames_dir=directory, interval_seconds=10.0)


if __name__ == "__main__":
    unittest.main()
