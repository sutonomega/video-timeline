from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_timeline.event_detector import DEFAULT_EVENT_KIND, calculate_importance_score, detect_events
from video_timeline.timeline_generator import TimelineEntry


class EventDetectorTest(unittest.TestCase):
    def test_detect_events_converts_timeline_entries_to_activity_events(self):
        timeline = [
            TimelineEntry(
                start_seconds=0.0,
                end_seconds=20.0,
                summary="ChatGPTで仕様相談をしている",
                frame_indices=[0, 1],
            ),
            TimelineEntry(
                start_seconds=20.0,
                end_seconds=35.0,
                summary="VSCodeで実装している",
                frame_indices=[2, 3],
            ),
        ]

        events = detect_events(timeline)

        self.assertEqual(
            [event.to_dict() for event in events],
            [
                {
                    "kind": DEFAULT_EVENT_KIND,
                    "start_seconds": 0.0,
                    "end_seconds": 20.0,
                    "summary": "ChatGPTで仕様相談をしている",
                    "timeline_index": 0,
                    "importance_score": 0.33,
                },
                {
                    "kind": DEFAULT_EVENT_KIND,
                    "start_seconds": 20.0,
                    "end_seconds": 35.0,
                    "summary": "VSCodeで実装している",
                    "timeline_index": 1,
                    "importance_score": 0.25,
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
            ),
            TimelineEntry(
                start_seconds=0.0,
                end_seconds=20.0,
                summary="ChatGPTで仕様相談をしている",
                frame_indices=[0, 1],
            ),
        ]

        events = detect_events(timeline)

        self.assertEqual([event.summary for event in events], ["ChatGPTで仕様相談をしている", "VSCodeで実装している"])
        self.assertEqual([event.timeline_index for event in events], [1, 0])

    def test_calculate_importance_score_uses_duration_with_bounds(self):
        self.assertEqual(
            calculate_importance_score(
                TimelineEntry(start_seconds=0.0, end_seconds=3.0, summary="短い作業", frame_indices=[0])
            ),
            0.1,
        )
        self.assertEqual(
            calculate_importance_score(
                TimelineEntry(start_seconds=0.0, end_seconds=30.0, summary="通常の作業", frame_indices=[0])
            ),
            0.5,
        )
        self.assertEqual(
            calculate_importance_score(
                TimelineEntry(start_seconds=0.0, end_seconds=120.0, summary="長い作業", frame_indices=[0])
            ),
            1.0,
        )


if __name__ == "__main__":
    unittest.main()
