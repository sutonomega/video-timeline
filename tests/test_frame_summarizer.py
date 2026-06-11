from pathlib import Path
import json
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_timeline.frame_extractor import ExtractedFrame
from video_timeline.frame_summarizer import (
    AnalysisMetadata,
    DEFAULT_VL_MODEL,
    DEFAULT_VL_PROVIDER,
    FrameSummarizerError,
    FrameSummary,
    build_frame_summary_document,
    save_frame_summary_json,
    summarize_frames,
    summarize_frames_with_ollama,
    summarize_image_with_ollama,
)
from video_timeline.video_loader import VideoMetadata


class FrameSummarizerTest(unittest.TestCase):
    def test_summarize_frames_sorts_by_time_and_keeps_frame_fields(self):
        frames = [
            ExtractedFrame(index=1, time_seconds=10.0, image="frames/000010000.jpg"),
            ExtractedFrame(index=0, time_seconds=0.0, image="frames/000000000.jpg"),
        ]

        summaries = summarize_frames(frames, lambda frame: f"{frame.time_seconds:g}秒の画面")

        self.assertEqual([summary.time_seconds for summary in summaries], [0.0, 10.0])
        self.assertEqual(
            [summary.to_dict() for summary in summaries],
            [
                {
                    "index": 0,
                    "time_seconds": 0.0,
                    "image": "frames/000000000.jpg",
                    "summary": "0秒の画面",
                },
                {
                    "index": 1,
                    "time_seconds": 10.0,
                    "image": "frames/000010000.jpg",
                    "summary": "10秒の画面",
                },
            ],
        )

    def test_summarize_frames_rejects_empty_summary(self):
        frames = [ExtractedFrame(index=0, time_seconds=0.0, image="frames/000000000.jpg")]

        with self.assertRaisesRegex(FrameSummarizerError, "空の要約"):
            summarize_frames(frames, lambda frame: " ")

    def test_summarize_frames_with_ollama_uses_frame_images(self):
        frames = [ExtractedFrame(index=0, time_seconds=0.0, image="frames/000000000.jpg")]

        with patch("video_timeline.frame_summarizer.summarize_image_with_ollama", return_value="仕様相談をしている") as summarize:
            summaries = summarize_frames_with_ollama(frames, model="qwen2.5vl:7b", api_url="http://ollama/api/generate")

        self.assertEqual(summaries[0].summary, "仕様相談をしている")
        summarize.assert_called_once_with(
            "frames/000000000.jpg",
            model="qwen2.5vl:7b",
            prompt="この画像でユーザーが何をしているかを日本語で1文で要約してください。",
            api_url="http://ollama/api/generate",
        )

    def test_build_frame_summary_document_contains_video_analysis_and_summaries(self):
        video = VideoMetadata(
            path="/tmp/input.mp4",
            duration_seconds=12.5,
            fps=30.0,
            frame_count=375,
            width=1920,
            height=1080,
        )
        analysis = AnalysisMetadata(interval_seconds=10.0)
        frame_summaries = [
            FrameSummary(index=0, time_seconds=0.0, image="frames/000000000.jpg", summary="仕様相談をしている")
        ]

        document = build_frame_summary_document(
            video=video,
            analysis=analysis,
            frame_summaries=frame_summaries,
            generated_at="2026-06-11T00:00:00Z",
        )

        self.assertEqual(document["version"], 1)
        self.assertEqual(document["generated_at"], "2026-06-11T00:00:00Z")
        self.assertEqual(document["video"]["path"], "/tmp/input.mp4")
        self.assertEqual(
            document["analysis"],
            {
                "interval_seconds": 10.0,
                "vl_provider": DEFAULT_VL_PROVIDER,
                "vl_model": DEFAULT_VL_MODEL,
            },
        )
        self.assertEqual(document["frame_summaries"][0]["summary"], "仕様相談をしている")

    def test_save_frame_summary_json_writes_utf8_json(self):
        document = {
            "version": 1,
            "generated_at": "2026-06-11T00:00:00Z",
            "video": {},
            "analysis": {},
            "frame_summaries": [{"summary": "日本語の要約"}],
        }

        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "nested" / "timeline.json"
            save_frame_summary_json(document, output_path)
            saved = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(saved["frame_summaries"][0]["summary"], "日本語の要約")

    def test_summarize_image_with_ollama_posts_image_and_returns_response(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return json.dumps({"response": "ChatGPTで仕様相談をしている"}).encode("utf-8")

        with TemporaryDirectory() as directory:
            image_path = Path(directory) / "frame.jpg"
            image_path.write_bytes(b"image-bytes")

            with patch("video_timeline.frame_summarizer.request.urlopen", return_value=FakeResponse()) as urlopen:
                summary = summarize_image_with_ollama(image_path, model="qwen2.5vl:7b", api_url="http://ollama/api/generate")

        self.assertEqual(summary, "ChatGPTで仕様相談をしている")
        http_request = urlopen.call_args.args[0]
        self.assertEqual(http_request.full_url, "http://ollama/api/generate")
        payload = json.loads(http_request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "qwen2.5vl:7b")
        self.assertFalse(payload["stream"])
        self.assertEqual(len(payload["images"]), 1)

    def test_summarize_image_with_ollama_rejects_empty_response(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return b'{"response": " "}'

        with TemporaryDirectory() as directory:
            image_path = Path(directory) / "frame.jpg"
            image_path.write_bytes(b"image-bytes")

            with patch("video_timeline.frame_summarizer.request.urlopen", return_value=FakeResponse()):
                with self.assertRaisesRegex(FrameSummarizerError, "要約文"):
                    summarize_image_with_ollama(image_path)

    def test_summarize_image_with_ollama_rejects_missing_image(self):
        with self.assertRaisesRegex(FrameSummarizerError, "画像ファイルが存在しません"):
            summarize_image_with_ollama("missing.jpg")


if __name__ == "__main__":
    unittest.main()
