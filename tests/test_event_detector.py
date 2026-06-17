from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_timeline.event_detector import DEFAULT_EVENT_KIND, calculate_importance_score, classify_event_kind, detect_events
from video_timeline.timeline_generator import TimelineEntry


class EventDetectorTest(unittest.TestCase):
    def test_detect_events_classifies_timeline_entries(self):
        timeline = [
            TimelineEntry(
                start_seconds=0.0,
                end_seconds=20.0,
                summary="ChatGPTで仕様相談をしている",
                frame_indices=[0, 1],
                tags=["chatgpt", "planning"],
            ),
            TimelineEntry(
                start_seconds=20.0,
                end_seconds=35.0,
                summary="VSCodeで実装している",
                frame_indices=[2, 3],
                tags=["vscode", "coding"],
            ),
        ]

        events = detect_events(timeline)

        self.assertEqual(
            [event.to_dict() for event in events],
            [
                {
                    "kind": "chat",
                    "start_seconds": 0.0,
                    "end_seconds": 20.0,
                    "summary": "ChatGPTで仕様相談をしている",
                    "timeline_index": 0,
                    "importance_score": 0.43,
                },
                {
                    "kind": "coding",
                    "start_seconds": 20.0,
                    "end_seconds": 35.0,
                    "summary": "VSCodeで実装している",
                    "timeline_index": 1,
                    "importance_score": 0.35,
                },
            ],
        )

    def test_detect_events_returns_empty_list_without_timeline(self):
        self.assertEqual(detect_events([]), [])

    def test_detect_events_sorts_by_time_and_keeps_original_timeline_index(self):
        timeline = [
            TimelineEntry(
                start_seconds=20.0,
                end_seconds=35.0,
                summary="VSCodeで実装している",
                frame_indices=[2, 3],
                tags=[],
            ),
            TimelineEntry(
                start_seconds=0.0,
                end_seconds=20.0,
                summary="ChatGPTで仕様相談をしている",
                frame_indices=[0, 1],
                tags=[],
            ),
        ]

        events = detect_events(timeline)

        self.assertEqual([event.summary for event in events], ["ChatGPTで仕様相談をしている", "VSCodeで実装している"])
        self.assertEqual([event.timeline_index for event in events], [1, 0])

    def test_classify_event_kind_uses_summary_and_tags(self):
        cases = [
            (TimelineEntry(0.0, 10.0, "GitHubでPRレビューしている", [0], ["github"]), "review"),
            (TimelineEntry(0.0, 10.0, "gitコマンドを実行している", [0], ["terminal"]), "terminal"),
            (TimelineEntry(0.0, 10.0, "Pythonコードを実装している", [0], ["python"]), "coding"),
            (TimelineEntry(0.0, 10.0, "ChatGPTで要件相談をしている", [0], []), "chat"),
            (TimelineEntry(0.0, 10.0, "お粥を調理している", [0], ["cooking"]), "cooking"),
            (TimelineEntry(0.0, 10.0, "YouTubeを見ている", [0], ["youtube"]), "browser"),
            (TimelineEntry(0.0, 10.0, "机の上を見ている", [0], []), DEFAULT_EVENT_KIND),
        ]

        for entry, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(classify_event_kind(entry), expected)

    def test_calculate_importance_score_uses_duration_with_bounds(self):
        self.assertEqual(
            calculate_importance_score(
                TimelineEntry(start_seconds=0.0, end_seconds=3.0, summary="短い作業", frame_indices=[0], tags=[])
            ),
            0.1,
        )
        self.assertEqual(
            calculate_importance_score(
                TimelineEntry(start_seconds=0.0, end_seconds=30.0, summary="通常の作業", frame_indices=[0], tags=[])
            ),
            0.5,
        )
        self.assertEqual(
            calculate_importance_score(
                TimelineEntry(start_seconds=0.0, end_seconds=120.0, summary="長い作業", frame_indices=[0], tags=[])
            ),
            1.0,
        )

    def test_calculate_importance_score_adds_kind_bonus(self):
        self.assertEqual(
            calculate_importance_score(
                TimelineEntry(0.0, 30.0, "PRレビューしている", [0], ["github"]),
                "review",
            ),
            0.65,
        )
        self.assertEqual(
            calculate_importance_score(
                TimelineEntry(0.0, 120.0, "VSCodeで実装している", [0], ["coding"]),
                "coding",
            ),
            1.0,
        )


if __name__ == "__main__":
    unittest.main()
