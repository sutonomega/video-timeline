from pathlib import Path
import json
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_timeline.timeline_searcher import (
    TimelineSearchError,
    TimelineSearchResult,
    format_search_result,
    format_timestamp,
    search_timeline_document,
    search_timeline_file,
)


class TimelineSearcherTest(unittest.TestCase):
    def test_search_timeline_document_matches_summary_tags_and_events(self):
        document = {
            "timeline": [
                {
                    "start_seconds": 80.0,
                    "end_seconds": 250.0,
                    "summary": "ChatGPTで仕様相談",
                    "tags": ["chatgpt", "planning"],
                },
                {
                    "start_seconds": 300.0,
                    "end_seconds": 360.0,
                    "summary": "VSCodeで実装",
                    "tags": ["vscode", "coding"],
                },
                {
                    "start_seconds": 420.0,
                    "end_seconds": 480.0,
                    "summary": "GitHubでPR確認",
                    "tags": ["github"],
                },
            ],
            "events": [
                {"timeline_index": 1, "kind": "coding", "summary": "Python実装"},
                {"timeline_index": 2, "kind": "review", "summary": "pull request review"},
            ],
        }

        self.assertEqual(
            search_timeline_document(document, "chatgpt"),
            [TimelineSearchResult(0, 80.0, 250.0, "ChatGPTで仕様相談")],
        )
        self.assertEqual(
            search_timeline_document(document, "CODING"),
            [TimelineSearchResult(1, 300.0, 360.0, "VSCodeで実装")],
        )
        self.assertEqual(
            search_timeline_document(document, "review"),
            [TimelineSearchResult(2, 420.0, 480.0, "GitHubでPR確認")],
        )

    def test_search_timeline_document_returns_empty_list_for_no_matches(self):
        document = {
            "timeline": [{"start_seconds": 0.0, "end_seconds": 10.0, "summary": "VSCodeで実装", "tags": []}]
        }

        self.assertEqual(search_timeline_document(document, "chatgpt"), [])

    def test_search_timeline_file_rejects_missing_file_and_invalid_query(self):
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(TimelineSearchError, "timeline JSONが存在しません"):
                search_timeline_file(Path(directory) / "missing.json", "chatgpt")

        with self.assertRaisesRegex(TimelineSearchError, "query"):
            search_timeline_document({"timeline": []}, " ")

    def test_search_timeline_file_loads_json(self):
        document = {
            "timeline": [
                {"start_seconds": 0.0, "end_seconds": 10.0, "summary": "GitHubでPR確認", "tags": ["github"]}
            ]
        }

        with TemporaryDirectory() as directory:
            path = Path(directory) / "timeline.json"
            path.write_text(json.dumps(document), encoding="utf-8")

            results = search_timeline_file(path, "github")

        self.assertEqual(results, [TimelineSearchResult(0, 0.0, 10.0, "GitHubでPR確認")])

    def test_format_search_result_formats_index_time_range_and_summary(self):
        result = TimelineSearchResult(3, 80.0, 250.0, "ChatGPTで仕様相談")

        self.assertEqual(format_search_result(result), "3  01:20-04:10  ChatGPTで仕様相談")

    def test_format_timestamp_uses_hours_when_needed(self):
        self.assertEqual(format_timestamp(59.4), "00:59")
        self.assertEqual(format_timestamp(3661.0), "01:01:01")


if __name__ == "__main__":
    unittest.main()
