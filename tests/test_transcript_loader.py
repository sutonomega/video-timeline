from pathlib import Path
import json
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_timeline.transcript_loader import (
    DEFAULT_TRANSCRIPT_SOURCE,
    TranscriptLoaderError,
    load_transcript_segments,
)


class TranscriptLoaderTest(unittest.TestCase):
    def test_load_transcript_segments_returns_empty_without_path(self):
        self.assertEqual(load_transcript_segments(None), [])

    def test_load_transcript_segments_reads_transcripts_key(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "transcript.json"
            path.write_text(
                json.dumps(
                    {
                        "transcripts": [
                            {
                                "start_seconds": 10.0,
                                "end_seconds": 15.5,
                                "text": "次はHTML出力を確認します",
                                "source": "manual",
                                "speaker": "user",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            segments = load_transcript_segments(path)

        self.assertEqual(
            [segment.to_dict() for segment in segments],
            [
                {
                    "start_seconds": 10.0,
                    "end_seconds": 15.5,
                    "text": "次はHTML出力を確認します",
                    "source": "manual",
                    "speaker": "user",
                }
            ],
        )

    def test_load_transcript_segments_reads_whisper_segments_key(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "whisper.json"
            path.write_text(
                json.dumps(
                    {
                        "segments": [
                            {"start": 5, "end": 8, "text": "フレーム要約を確認しています"},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            segments = load_transcript_segments(path)

        self.assertEqual(segments[0].start_seconds, 5.0)
        self.assertEqual(segments[0].end_seconds, 8.0)
        self.assertEqual(segments[0].text, "フレーム要約を確認しています")
        self.assertEqual(segments[0].source, DEFAULT_TRANSCRIPT_SOURCE)
        self.assertIsNone(segments[0].speaker)

    def test_load_transcript_segments_sorts_by_time(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "transcript.json"
            path.write_text(
                json.dumps(
                    [
                        {"start_seconds": 20, "end_seconds": 25, "text": "後半"},
                        {"start_seconds": 0, "end_seconds": 5, "text": "前半"},
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            segments = load_transcript_segments(path)

        self.assertEqual([segment.text for segment in segments], ["前半", "後半"])

    def test_load_transcript_segments_rejects_invalid_range(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "transcript.json"
            path.write_text(
                json.dumps([{"start_seconds": 10, "end_seconds": 10, "text": "同時刻"}], ensure_ascii=False),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(TranscriptLoaderError, "end_seconds"):
                load_transcript_segments(path)

    def test_load_transcript_segments_rejects_missing_text(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "transcript.json"
            path.write_text(
                json.dumps([{"start_seconds": 0, "end_seconds": 1}], ensure_ascii=False),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(TranscriptLoaderError, "text"):
                load_transcript_segments(path)

    def test_load_transcript_segments_rejects_invalid_json(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "transcript.json"
            path.write_text("{", encoding="utf-8")

            with self.assertRaisesRegex(TranscriptLoaderError, "読み取れません"):
                load_transcript_segments(path)


if __name__ == "__main__":
    unittest.main()
