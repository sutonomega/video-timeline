from pathlib import Path
import json
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_timeline.timeline_html_exporter import (
    TimelineHtmlExportError,
    build_timeline_html_document,
    export_timeline_html_file,
)


class TimelineHtmlExporterTest(unittest.TestCase):
    def test_build_timeline_html_document_renders_video_timeline_and_events(self):
        document = {
            "video": {
                "path": "/tmp/input.mp4",
                "duration_seconds": 125.5,
                "width": 1920,
                "height": 1080,
            },
            "analysis": {
                "interval_seconds": 10,
                "vl_provider": "ollama",
                "vl_model": "qwen2.5vl:7b",
            },
            "timeline": [
                {
                    "start_seconds": 80.9,
                    "end_seconds": 250.2,
                    "summary": "ChatGPTで仕様相談",
                    "tags": ["chatgpt", "planning"],
                }
            ],
            "events": [
                {
                    "kind": "activity",
                    "start_seconds": 80.9,
                    "end_seconds": 250.2,
                    "summary": "ChatGPTで仕様相談",
                    "timeline_index": 0,
                    "importance_score": 0.42,
                    "tags": ["chatgpt"],
                }
            ],
        }

        html = build_timeline_html_document(document)

        self.assertIn("<h1>Video Timeline</h1>", html)
        self.assertIn("/tmp/input.mp4", html)
        self.assertIn("qwen2.5vl:7b", html)
        self.assertIn("<th>index</th><th>time</th><th>summary</th><th>tags</th>", html)
        self.assertIn("<td>0</td><td>01:20-04:10</td><td>ChatGPTで仕様相談</td><td>chatgpt, planning</td>", html)
        self.assertIn("<th>kind</th><th>time</th><th>summary</th>", html)
        self.assertIn("<td>activity</td><td>01:20-04:10</td><td>ChatGPTで仕様相談</td><td>0</td><td>0.42</td>", html)

    def test_build_timeline_html_document_escapes_values(self):
        document = {
            "video": {"path": "/tmp/<input>.mp4"},
            "analysis": {},
            "timeline": [
                {
                    "start_seconds": 0,
                    "end_seconds": 10,
                    "summary": "<script>alert(1)</script>",
                    "tags": ["chatgpt&review"],
                }
            ],
        }

        html = build_timeline_html_document(document)

        self.assertIn("/tmp/&lt;input&gt;.mp4", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertIn("chatgpt&amp;review", html)
        self.assertNotIn("<script>alert(1)</script>", html)

    def test_build_timeline_html_document_requires_timeline(self):
        with self.assertRaisesRegex(TimelineHtmlExportError, "timelineがありません"):
            build_timeline_html_document({"video": {}, "analysis": {}})

    def test_export_timeline_html_file_writes_static_html(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            timeline_json = root / "timeline.json"
            output_html = root / "exports" / "timeline.html"
            timeline_json.write_text(
                json.dumps(
                    {
                        "video": {"path": "/tmp/input.mp4"},
                        "analysis": {"interval_seconds": 10},
                        "timeline": [
                            {
                                "start_seconds": 0,
                                "end_seconds": 10,
                                "summary": "GitHubでPRレビュー",
                                "tags": ["github", "review"],
                            }
                        ],
                        "events": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = export_timeline_html_file(timeline_json, output_html)

            self.assertEqual(result, output_html)
            self.assertIn("GitHubでPRレビュー", output_html.read_text(encoding="utf-8"))

    def test_export_timeline_html_file_rejects_invalid_json(self):
        with TemporaryDirectory() as directory:
            timeline_json = Path(directory) / "timeline.json"
            timeline_json.write_text("{", encoding="utf-8")

            with self.assertRaisesRegex(TimelineHtmlExportError, "読み取れません"):
                export_timeline_html_file(timeline_json, Path(directory) / "timeline.html")


if __name__ == "__main__":
    unittest.main()
