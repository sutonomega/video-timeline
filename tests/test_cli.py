from pathlib import Path
import io
import json
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_timeline.cli import main
from video_timeline.frame_extractor import ExtractedFrame
from video_timeline.frame_summarizer import FrameSummary
from video_timeline.video_loader import VideoMetadata


class CliTest(unittest.TestCase):
    def test_cli_connects_video_to_frame_summary_json(self):
        video = VideoMetadata(
            path="/tmp/input.mp4",
            duration_seconds=12.5,
            fps=30.0,
            frame_count=375,
            width=1920,
            height=1080,
        )
        frames = [ExtractedFrame(index=0, time_seconds=0.0, image="frames/000000000.jpg")]
        summaries = [
            FrameSummary(
                index=0,
                time_seconds=0.0,
                image="frames/000000000.jpg",
                summary="ChatGPTで仕様相談をしている",
            )
        ]

        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "timeline.json"
            with (
                patch("video_timeline.cli.load_video_metadata", return_value=video) as load_video,
                patch("video_timeline.cli.extract_frames", return_value=frames) as extract,
                patch("video_timeline.cli.summarize_frames_with_ollama", return_value=summaries) as summarize,
            ):
                with patch("sys.stdout", new_callable=io.StringIO):
                    exit_code = main(
                        [
                            "input.mp4",
                            "--output",
                            str(output_path),
                            "--interval-seconds",
                            "5",
                            "--frames-dir",
                            "custom_frames",
                        ]
                    )

            saved = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        load_video.assert_called_once_with("input.mp4")
        extract.assert_called_once_with(video, frames_dir="custom_frames", interval_seconds=5.0)
        summarize.assert_called_once_with(frames, model="qwen2.5vl:7b")
        self.assertEqual(saved["video"]["path"], "/tmp/input.mp4")
        self.assertEqual(saved["analysis"]["interval_seconds"], 5.0)
        self.assertEqual(saved["analysis"]["vl_provider"], "ollama")
        self.assertEqual(saved["analysis"]["vl_model"], "qwen2.5vl:7b")
        self.assertEqual(saved["frame_summaries"][0]["summary"], "ChatGPTで仕様相談をしている")

    def test_cli_returns_error_for_pipeline_failure(self):
        with patch("video_timeline.cli.load_video_metadata", side_effect=ValueError("failed")):
            with patch("sys.stderr", new_callable=io.StringIO):
                exit_code = main(["input.mp4", "--output", "timeline.json"])

        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
