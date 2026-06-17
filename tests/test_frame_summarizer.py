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
    FrameSummaryContent,
    StorageMetadata,
    build_frame_summary_document,
    normalize_tags,
    parse_frame_summary_response,
    save_frame_summary_json,
    summarize_frames,
    summarize_frames_with_ollama,
    summarize_image_with_ollama,
)
from video_timeline.event_detector import EventCandidate
from video_timeline.video_loader import VideoMetadata


class FrameSummarizerTest(unittest.TestCase):
    def test_summarize_frames_sorts_by_time_and_keeps_frame_fields(self):
        frames = [
            ExtractedFrame(index=1, time_seconds=10.0, image="frames/000010000.jpg"),
            ExtractedFrame(index=0, time_seconds=0.0, image="frames/000000000.jpg"),
        ]

        summaries = summarize_frames(
            frames,
            lambda frame: FrameSummaryContent(
                summary=f"{frame.time_seconds:g}秒の画面",
                tags=("ChatGPT", "PR Review"),
            ),
        )

        self.assertEqual([summary.time_seconds for summary in summaries], [0.0, 10.0])
        self.assertEqual(
            [summary.to_dict() for summary in summaries],
            [
                {
                    "index": 0,
                    "time_seconds": 0.0,
                    "image": "frames/000000000.jpg",
                    "summary": "0秒の画面",
                    "primary_tag": "chatgpt",
                    "secondary_tags": ["pr_review"],
                    "tags": ["chatgpt", "pr_review"],
                },
                {
                    "index": 1,
                    "time_seconds": 10.0,
                    "image": "frames/000010000.jpg",
                    "summary": "10秒の画面",
                    "primary_tag": "chatgpt",
                    "secondary_tags": ["pr_review"],
                    "tags": ["chatgpt", "pr_review"],
                },
            ],
        )

    def test_summarize_frames_reports_progress_in_sorted_order(self):
        frames = [
            ExtractedFrame(index=1, time_seconds=10.0, image="frames/000010000.jpg"),
            ExtractedFrame(index=0, time_seconds=0.0, image="frames/000000000.jpg"),
        ]
        progress_calls = []

        summarize_frames(
            frames,
            lambda frame: f"{frame.time_seconds:g}秒の画面",
            progress=lambda current, total, frame: progress_calls.append((current, total, frame.index)),
        )

        self.assertEqual(progress_calls, [(1, 2, 0), (2, 2, 1)])

    def test_summarize_frames_rejects_empty_summary(self):
        frames = [ExtractedFrame(index=0, time_seconds=0.0, image="frames/000000000.jpg")]

        with self.assertRaisesRegex(FrameSummarizerError, "空の要約"):
            summarize_frames(frames, lambda frame: " ")

    def test_summarize_frames_with_ollama_uses_frame_images(self):
        frames = [ExtractedFrame(index=0, time_seconds=0.0, image="frames/000000000.jpg")]

        with patch("video_timeline.frame_summarizer.summarize_image_with_ollama", return_value="仕様相談をしている") as summarize:
            summaries = summarize_frames_with_ollama(frames, model="qwen2.5vl:7b", api_url="http://ollama/api/generate")

        self.assertEqual(summaries[0].summary, "仕様相談をしている")
        self.assertEqual(summaries[0].tags, ())
        summarize.assert_called_once_with(
            "frames/000000000.jpg",
            model="qwen2.5vl:7b",
            prompt=(
                "この画像でユーザーが何をしているかを日本語で1文で要約してください。"
                "画面の主対象をprimary_tagに1つだけ入れ、補助的な作業や文脈をsecondary_tagsに入れてください。"
                "PCやスマホの画面が主対象ならprimary_tagは次から選んでください: "
                "chatgpt, github, vscode, terminal, browser, youtube, discord, game, document。"
                "料理、食事、家事、外出、移動などの生活動画が主対象ならprimary_tagは次から選んでください: "
                "cooking, oatmeal, rice_cooker, eating, shopping, walking, exercise, cleaning, travel, study。"
                "適切な候補がない場合は、短い自由タグを使ってください。"
                "secondary_tagsは必ず配列キーsecondary_tagsとして返してください。secondary_tags[]は使わないでください。"
                '必ずJSONだけで返してください。形式: {"summary":"日本語の要約","primary_tag":"chatgpt","secondary_tags":["planning"]}'
            ),
            api_url="http://ollama/api/generate",
        )

    def test_summarize_frames_with_ollama_passes_progress_callback(self):
        frames = [ExtractedFrame(index=0, time_seconds=0.0, image="frames/000000000.jpg")]
        progress_calls = []

        with patch("video_timeline.frame_summarizer.summarize_image_with_ollama", return_value="仕様相談をしている"):
            summarize_frames_with_ollama(
                frames,
                model="qwen2.5vl:7b",
                api_url="http://ollama/api/generate",
                progress=lambda current, total, frame: progress_calls.append((current, total, frame.index)),
            )

        self.assertEqual(progress_calls, [(1, 1, 0)])

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
            FrameSummary(
                index=0,
                time_seconds=0.0,
                image="frames/000000000.jpg",
                summary="仕様相談をしている",
                tags=("chatgpt", "planning"),
            )
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
        self.assertEqual(document["frame_summaries"][0]["primary_tag"], "chatgpt")
        self.assertEqual(document["frame_summaries"][0]["secondary_tags"], ["planning"])
        self.assertEqual(document["frame_summaries"][0]["tags"], ["chatgpt", "planning"])

    def test_build_frame_summary_document_includes_timeline_when_given(self):
        class Timeline:
            def to_dict(self):
                return {
                    "start_seconds": 0.0,
                    "end_seconds": 10.0,
                    "summary": "仕様相談をしている",
                    "frame_indices": [0],
                }

        video = VideoMetadata(
            path="/tmp/input.mp4",
            duration_seconds=10.0,
            fps=30.0,
            frame_count=300,
            width=1920,
            height=1080,
        )
        analysis = AnalysisMetadata(interval_seconds=10.0)

        document = build_frame_summary_document(
            video=video,
            analysis=analysis,
            frame_summaries=[],
            timeline=[Timeline()],
            generated_at="2026-06-11T00:00:00Z",
        )

        self.assertEqual(
            document["timeline"],
            [
                {
                    "start_seconds": 0.0,
                    "end_seconds": 10.0,
                    "summary": "仕様相談をしている",
                    "frame_indices": [0],
                }
            ],
        )

    def test_build_frame_summary_document_includes_storage_when_given(self):
        video = VideoMetadata(
            path="/mnt/storage/videos/input.mp4",
            duration_seconds=10.0,
            fps=30.0,
            frame_count=300,
            width=1920,
            height=1080,
        )
        analysis = AnalysisMetadata(interval_seconds=10.0)

        document = build_frame_summary_document(
            video=video,
            analysis=analysis,
            storage=StorageMetadata(
                video_path="/mnt/storage/videos/input.mp4",
                frames_dir="/mnt/storage/frames/input_abcd1234ef56",
                timeline_path="/mnt/storage/timelines/input.json",
            ),
            frame_summaries=[],
            generated_at="2026-06-11T00:00:00Z",
        )

        self.assertEqual(
            document["storage"],
            {
                "video_path": "/mnt/storage/videos/input.mp4",
                "frames_dir": "/mnt/storage/frames/input_abcd1234ef56",
                "timeline_path": "/mnt/storage/timelines/input.json",
            },
        )

    def test_build_frame_summary_document_includes_events_when_given(self):
        video = VideoMetadata(
            path="/tmp/input.mp4",
            duration_seconds=10.0,
            fps=30.0,
            frame_count=300,
            width=1920,
            height=1080,
        )
        analysis = AnalysisMetadata(interval_seconds=10.0)
        events = [
            EventCandidate(
                kind="activity",
                start_seconds=0.0,
                end_seconds=10.0,
                summary="仕様相談をしている",
                timeline_index=0,
                importance_score=0.17,
            )
        ]

        document = build_frame_summary_document(
            video=video,
            analysis=analysis,
            frame_summaries=[],
            events=events,
            generated_at="2026-06-11T00:00:00Z",
        )

        self.assertEqual(
            document["events"],
            [
                {
                    "kind": "activity",
                    "start_seconds": 0.0,
                    "end_seconds": 10.0,
                    "summary": "仕様相談をしている",
                    "timeline_index": 0,
                    "importance_score": 0.17,
                }
            ],
        )

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

    def test_summarize_image_with_ollama_posts_image_and_returns_response_json(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return json.dumps(
                    {
                        "response": json.dumps(
                            {
                                "summary": "ChatGPTで仕様相談をしている",
                                "tags": ["ChatGPT", "PR Review", "chatgpt"],
                            }
                        )
                    }
                ).encode("utf-8")

        with TemporaryDirectory() as directory:
            image_path = Path(directory) / "frame.jpg"
            image_path.write_bytes(b"image-bytes")

            with patch("video_timeline.frame_summarizer.request.urlopen", return_value=FakeResponse()) as urlopen:
                content = summarize_image_with_ollama(image_path, model="qwen2.5vl:7b", api_url="http://ollama/api/generate")

        self.assertEqual(content.summary, "ChatGPTで仕様相談をしている")
        self.assertEqual(content.tags, ("chatgpt", "pr_review"))
        http_request = urlopen.call_args.args[0]
        self.assertEqual(http_request.full_url, "http://ollama/api/generate")
        payload = json.loads(http_request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "qwen2.5vl:7b")
        self.assertFalse(payload["stream"])
        self.assertEqual(len(payload["images"]), 1)

    def test_parse_frame_summary_response_falls_back_to_plain_text(self):
        content = parse_frame_summary_response("ChatGPTで仕様相談をしている")

        self.assertEqual(content.summary, "ChatGPTで仕様相談をしている")
        self.assertEqual(content.tags, ())

    def test_parse_frame_summary_response_rejects_tags_without_summary(self):
        with self.assertRaisesRegex(FrameSummarizerError, "要約文"):
            parse_frame_summary_response(json.dumps({"tags": ["chatgpt"]}))

    def test_parse_frame_summary_response_supports_primary_and_secondary_tags(self):
        content = parse_frame_summary_response(
            json.dumps(
                {
                    "summary": "GitHubでPRを確認している",
                    "primary_tag": "GitHub",
                    "secondary_tags": ["PR Review", "github"],
                }
            )
        )

        self.assertEqual(content.summary, "GitHubでPRを確認している")
        self.assertEqual(content.primary_tag, "github")
        self.assertEqual(content.secondary_tags, ("pr_review",))
        self.assertEqual(content.tags, ("github", "pr_review"))

    def test_parse_frame_summary_response_extracts_json_from_wrapped_text(self):
        content = parse_frame_summary_response(
            "解析結果です。\n"
            "```json\n"
            '{"summary":"料理をしている","primary_tag":"cooking","secondary_tags":["oatmeal"]}'
            "\n```\n"
            "以上です。"
        )

        self.assertEqual(content.summary, "料理をしている")
        self.assertEqual(content.primary_tag, "cooking")
        self.assertEqual(content.secondary_tags, ("oatmeal",))
        self.assertEqual(content.tags, ("cooking", "oatmeal"))

    def test_parse_frame_summary_response_repairs_secondary_tags_brackets(self):
        content = parse_frame_summary_response(
            json.dumps(
                {
                    "summary": "お粥を混ぜる",
                    "primary_tag": "cooking",
                    "secondary_tags[]": ["oatmeal"],
                }
            )
        )

        self.assertEqual(content.summary, "お粥を混ぜる")
        self.assertEqual(content.primary_tag, "cooking")
        self.assertEqual(content.secondary_tags, ("oatmeal",))
        self.assertEqual(content.tags, ("cooking", "oatmeal"))

    def test_parse_frame_summary_response_recovers_partial_unclosed_json(self):
        content = parse_frame_summary_response(
            '{"summary":"フライパンをIHクッキングヒーターに置く","primary_tag":"cooking","secondary_tags[]}'
        )

        self.assertEqual(content.summary, "フライパンをIHクッキングヒーターに置く")
        self.assertEqual(content.primary_tag, "cooking")
        self.assertEqual(content.secondary_tags, ())
        self.assertEqual(content.tags, ("cooking",))

    def test_parse_frame_summary_response_extracts_nested_json_summary(self):
        content = parse_frame_summary_response(
            json.dumps(
                {
                    "summary": json.dumps(
                        {
                            "summary": "フライパンをIHクッキングヒーターに置く",
                            "primary_tag": "cooking",
                            "secondary_tags": ["cooking"],
                        }
                    ),
                    "primary_tag": "other",
                    "secondary_tags": [],
                }
            )
        )

        self.assertEqual(content.summary, "フライパンをIHクッキングヒーターに置く")
        self.assertEqual(content.primary_tag, "cooking")
        self.assertEqual(content.secondary_tags, ())
        self.assertEqual(content.tags, ("cooking",))

    def test_parse_frame_summary_response_derives_primary_tag_from_legacy_tags(self):
        content = parse_frame_summary_response(
            json.dumps(
                {
                    "summary": "ChatGPTで仕様相談をしている",
                    "tags": ["ChatGPT", "planning"],
                }
            )
        )

        self.assertEqual(content.primary_tag, "chatgpt")
        self.assertEqual(content.secondary_tags, ("planning",))
        self.assertEqual(content.tags, ("chatgpt", "planning"))

    def test_normalize_tags_keeps_lowercase_alnum_underscore_and_japanese_tags(self):
        self.assertEqual(
            normalize_tags(["ChatGPT", "PR Review", "terminal-test", "日本語", "将棋 対局", "chatgpt", 123]),
            ("chatgpt", "pr_review", "terminal_test", "日本語", "将棋_対局"),
        )

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
