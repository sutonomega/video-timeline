from pathlib import Path
import io
import json
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import ANY, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_timeline.cli import FrameSummarizationProgress, build_run_frames_dir, format_duration, main
from video_timeline.event_detector import EventCandidate
from video_timeline.frame_extractor import ExtractedFrame
from video_timeline.frame_summarizer import FrameSummary
from video_timeline.timeline_generator import TimelineEntry
from video_timeline.video_loader import VideoMetadata


class CliTest(unittest.TestCase):
    def test_format_duration_formats_seconds_minutes_and_hours(self):
        self.assertEqual(format_duration(12), "12s")
        self.assertEqual(format_duration(90), "1m 30s")
        self.assertEqual(format_duration(3661), "1h 1m 1s")

    def test_frame_summarization_progress_reports_remaining_time(self):
        frames = [
            ExtractedFrame(index=0, time_seconds=0.0, image="frames/000000000.jpg"),
            ExtractedFrame(index=1, time_seconds=10.0, image="frames/000010000.jpg"),
        ]

        with (
            patch("video_timeline.cli.time.monotonic", side_effect=[100.0, 130.0]),
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            progress = FrameSummarizationProgress()
            progress(1, 2, frames[0])
            progress(2, 2, frames[1])

        output = stdout.getvalue()
        self.assertIn("frame summarization started: 1/2 (0s, remaining: calculating)", output)
        self.assertIn("frame summarization started: 2/2 (10s, remaining: 30s)", output)

    def test_build_run_frames_dir_appends_video_stem_and_path_hash(self):
        run_dir = build_run_frames_dir("videos/demo.mp4", "frames")

        self.assertEqual(run_dir.parent, Path("frames"))
        self.assertRegex(run_dir.name, r"^demo_[0-9a-f]{12}$")
        self.assertEqual(
            build_run_frames_dir("videos/demo.mp4", "frames"),
            run_dir,
        )

    def test_build_run_frames_dir_avoids_same_filename_collision(self):
        self.assertNotEqual(
            build_run_frames_dir("/tmp/videos/a/sample.mp4", "frames"),
            build_run_frames_dir("/tmp/videos/b/sample.mp4", "frames"),
        )

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
        timeline = [
            TimelineEntry(
                start_seconds=0.0,
                end_seconds=12.5,
                summary="ChatGPTで仕様相談をしている",
                frame_indices=[0],
            )
        ]
        events = [
            EventCandidate(
                kind="activity",
                start_seconds=0.0,
                end_seconds=12.5,
                summary="ChatGPTで仕様相談をしている",
                timeline_index=0,
                importance_score=0.21,
            )
        ]

        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "timeline.json"
            with (
                patch("video_timeline.cli.load_video_metadata", return_value=video) as load_video,
                patch("video_timeline.cli.extract_frames", return_value=frames) as extract,
                patch("video_timeline.cli.summarize_frames_with_ollama", return_value=summaries) as summarize,
                patch("video_timeline.cli.build_timeline", return_value=timeline) as build_timeline,
                patch("video_timeline.cli.detect_events", return_value=events) as detect_events,
            ):
                with patch("sys.stdout", new_callable=io.StringIO) as stdout:
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
            output = stdout.getvalue()

        self.assertEqual(exit_code, 0)
        load_video.assert_called_once_with("input.mp4")
        extract.assert_called_once_with(
            video,
            frames_dir=build_run_frames_dir(video.path, "custom_frames"),
            interval_seconds=5.0,
        )
        summarize.assert_called_once_with(frames, model="qwen2.5vl:7b", progress=ANY)
        build_timeline.assert_called_once_with(summaries, video)
        detect_events.assert_called_once_with(timeline)
        self.assertIn("動画メタデータ取得中", output)
        self.assertIn("フレーム抽出中", output)
        self.assertIn("フレーム要約中", output)
        self.assertIn("タイムライン生成中", output)
        self.assertIn("イベント生成中", output)
        self.assertIn("JSON保存中", output)
        self.assertIn(f"wrote {output_path}", output)
        self.assertEqual(saved["video"]["path"], "/tmp/input.mp4")
        self.assertEqual(saved["analysis"]["interval_seconds"], 5.0)
        self.assertEqual(saved["analysis"]["vl_provider"], "ollama")
        self.assertEqual(saved["analysis"]["vl_model"], "qwen2.5vl:7b")
        self.assertEqual(saved["frame_summaries"][0]["summary"], "ChatGPTで仕様相談をしている")
        self.assertEqual(
            saved["timeline"],
            [
                {
                    "start_seconds": 0.0,
                    "end_seconds": 12.5,
                    "summary": "ChatGPTで仕様相談をしている",
                    "frame_indices": [0],
                }
            ],
        )
        self.assertEqual(
            saved["events"],
            [
                {
                    "kind": "activity",
                    "start_seconds": 0.0,
                    "end_seconds": 12.5,
                    "summary": "ChatGPTで仕様相談をしている",
                    "timeline_index": 0,
                    "importance_score": 0.21,
                }
            ],
        )

    def test_cli_returns_error_for_pipeline_failure(self):
        with patch("video_timeline.cli.load_video_metadata", side_effect=ValueError("failed")):
            with (
                patch("sys.stdout", new_callable=io.StringIO),
                patch("sys.stderr", new_callable=io.StringIO),
            ):
                exit_code = main(["input.mp4", "--output", "timeline.json"])

        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
