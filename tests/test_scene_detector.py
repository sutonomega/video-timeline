from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_timeline.scene_detector import (
    SCENE_DETECTOR_SOURCE,
    SceneBoundary,
    SceneDetectorError,
    detect_scene_boundaries,
    parse_ffmpeg_scene_metadata,
    safe_detect_scene_boundaries,
)


class SceneDetectorTest(unittest.TestCase):
    def test_parse_ffmpeg_scene_metadata_reads_times_and_scores(self):
        output = "\n".join(
            [
                "frame:0 pts:100 pts_time:10.5",
                "lavfi.scene_score=0.456",
                "frame:1 pts:200 pts_time:20",
                "lavfi.scene_score=0.789",
            ]
        )

        boundaries = parse_ffmpeg_scene_metadata(output)

        self.assertEqual(
            [boundary.to_dict() for boundary in boundaries],
            [
                {"time_seconds": 10.5, "source": SCENE_DETECTOR_SOURCE, "score": 0.456},
                {"time_seconds": 20.0, "source": SCENE_DETECTOR_SOURCE, "score": 0.789},
            ],
        )

    def test_parse_ffmpeg_scene_metadata_deduplicates_times(self):
        output = "\n".join(
            [
                "frame:0 pts:100 pts_time:10.0004",
                "lavfi.scene_score=0.456",
                "frame:1 pts:101 pts_time:10.00049",
                "lavfi.scene_score=0.5",
            ]
        )

        boundaries = parse_ffmpeg_scene_metadata(output)

        self.assertEqual(len(boundaries), 1)
        self.assertEqual(boundaries[0].time_seconds, 10.0004)

    def test_detect_scene_boundaries_runs_ffmpeg_and_parses_output(self):
        completed = type(
            "Completed",
            (),
            {
                "stdout": "frame:0 pts:100 pts_time:12.25\nlavfi.scene_score=0.6",
                "stderr": "",
            },
        )()

        with patch("video_timeline.scene_detector.subprocess.run", return_value=completed) as run:
            boundaries = detect_scene_boundaries("/tmp/input.mp4", threshold=0.35)

        run.assert_called_once()
        command = run.call_args.args[0]
        self.assertIn("ffmpeg", command)
        self.assertIn("select='gt(scene,0.35)',metadata=print", command)
        self.assertEqual(boundaries, [SceneBoundary(time_seconds=12.25, score=0.6)])

    def test_detect_scene_boundaries_rejects_invalid_threshold(self):
        with self.assertRaisesRegex(SceneDetectorError, "scene threshold"):
            detect_scene_boundaries("/tmp/input.mp4", threshold=1.5)

    def test_safe_detect_scene_boundaries_returns_empty_on_error(self):
        with patch("video_timeline.scene_detector.detect_scene_boundaries", side_effect=SceneDetectorError("failed")):
            self.assertEqual(safe_detect_scene_boundaries("/tmp/input.mp4"), [])


if __name__ == "__main__":
    unittest.main()
