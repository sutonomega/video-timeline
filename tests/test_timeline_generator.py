from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_timeline.frame_summarizer import FrameSummary
from video_timeline.timeline_generator import are_similar_summaries, build_timeline
from video_timeline.video_loader import VideoMetadata


class TimelineGeneratorTest(unittest.TestCase):
    def test_build_timeline_groups_consecutive_equal_summaries(self):
        video = VideoMetadata(
            path="/tmp/input.mp4",
            duration_seconds=35.0,
            fps=30.0,
            frame_count=1050,
            width=1920,
            height=1080,
        )
        summaries = [
            FrameSummary(index=0, time_seconds=0.0, image="frames/000000000.jpg", summary="ChatGPTで仕様相談をしている"),
            FrameSummary(index=1, time_seconds=10.0, image="frames/000010000.jpg", summary=" ChatGPTで仕様相談をしている "),
            FrameSummary(index=2, time_seconds=20.0, image="frames/000020000.jpg", summary="VSCodeで実装している"),
            FrameSummary(index=3, time_seconds=30.0, image="frames/000030000.jpg", summary="VSCodeで実装している"),
        ]

        timeline = build_timeline(summaries, video)

        self.assertEqual(
            [entry.to_dict() for entry in timeline],
            [
                {
                    "start_seconds": 0.0,
                    "end_seconds": 20.0,
                    "summary": "ChatGPTで仕様相談をしている",
                    "frame_indices": [0, 1],
                },
                {
                    "start_seconds": 20.0,
                    "end_seconds": 35.0,
                    "summary": "VSCodeで実装している",
                    "frame_indices": [2, 3],
                },
            ],
        )

    def test_build_timeline_groups_consecutive_similar_summaries(self):
        video = VideoMetadata(
            path="/tmp/input.mp4",
            duration_seconds=30.0,
            fps=30.0,
            frame_count=900,
            width=1920,
            height=1080,
        )
        summaries = [
            FrameSummary(index=0, time_seconds=0.0, image="frames/000000000.jpg", summary="ユーザーはChatGPTの仕様について議論しているようです。"),
            FrameSummary(index=1, time_seconds=10.0, image="frames/000010000.jpg", summary="ユーザーはChatGPTの要件について議論しているようです。"),
            FrameSummary(index=2, time_seconds=20.0, image="frames/000020000.jpg", summary="ユーザーはターミナルでテスト実行を行っている。"),
        ]

        timeline = build_timeline(summaries, video)

        self.assertEqual(
            [entry.to_dict() for entry in timeline],
            [
                {
                    "start_seconds": 0.0,
                    "end_seconds": 20.0,
                    "summary": "ユーザーはChatGPTの仕様について議論しているようです。",
                    "frame_indices": [0, 1],
                },
                {
                    "start_seconds": 20.0,
                    "end_seconds": 30.0,
                    "summary": "ユーザーはターミナルでテスト実行を行っている。",
                    "frame_indices": [2],
                },
            ],
        )

    def test_are_similar_summaries_keeps_different_work_separate(self):
        self.assertFalse(
            are_similar_summaries(
                "ユーザーはChatGPTの仕様について議論しているようです。",
                "ユーザーはターミナルでテスト実行を行っている。",
            )
        )

    def test_build_timeline_sorts_by_time_and_index(self):
        video = VideoMetadata(
            path="/tmp/input.mp4",
            duration_seconds=20.0,
            fps=30.0,
            frame_count=600,
            width=1920,
            height=1080,
        )
        summaries = [
            FrameSummary(index=2, time_seconds=10.0, image="frames/000010000-2.jpg", summary="実装している"),
            FrameSummary(index=1, time_seconds=10.0, image="frames/000010000-1.jpg", summary="実装している"),
            FrameSummary(index=0, time_seconds=0.0, image="frames/000000000.jpg", summary="仕様相談をしている"),
        ]

        timeline = build_timeline(summaries, video)

        self.assertEqual(timeline[1].frame_indices, [1, 2])

    def test_build_timeline_returns_empty_list_without_summaries(self):
        video = VideoMetadata(
            path="/tmp/input.mp4",
            duration_seconds=20.0,
            fps=30.0,
            frame_count=600,
            width=1920,
            height=1080,
        )

        self.assertEqual(build_timeline([], video), [])


if __name__ == "__main__":
    unittest.main()
