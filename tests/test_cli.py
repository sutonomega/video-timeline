from pathlib import Path
import io
import json
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import ANY, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_timeline.cli import (
    FrameExtractionProgress,
    FrameSummarizationProgress,
    SceneDetectionProgress,
    build_batch_video_dir,
    build_run_frames_dir,
    discover_mp4_files,
    format_duration,
    main,
)
from video_timeline.event_detector import EventCandidate
from video_timeline.frame_extractor import ExtractedFrame
from video_timeline.frame_summarizer import FrameSummary
from video_timeline.scene_detector import SceneBoundary
from video_timeline.app_config import AppConfig, StoragePathConfig
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

    def test_frame_extraction_progress_reports_current_total_and_time(self):
        with patch("sys.stdout", new_callable=io.StringIO) as stdout:
            progress = FrameExtractionProgress()
            progress(3, 120, 20.0)

        self.assertIn("frame extraction progress: 3/120 (00:20)", stdout.getvalue())

    def test_scene_detection_progress_reports_processed_time_and_percent(self):
        with patch("sys.stdout", new_callable=io.StringIO) as stdout:
            progress = SceneDetectionProgress(duration_seconds=600.0)
            progress(80.0)
            progress(80.4)
            progress(120.0)

        output = stdout.getvalue()
        self.assertIn("scene detection progress: 01:20/10:00 (13%)", output)
        self.assertEqual(output.count("scene detection progress"), 2)

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

    def test_discover_mp4_files_recurses_without_collecting_non_mp4_files(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "b").mkdir()
            (root / "a").mkdir()
            first = root / "a" / "first.mp4"
            second = root / "b" / "second.MP4"
            ignored = root / "b" / "note.txt"
            first.write_text("", encoding="utf-8")
            second.write_text("", encoding="utf-8")
            ignored.write_text("", encoding="utf-8")

            self.assertCountEqual(list(discover_mp4_files(root)), [first, second])

    def test_build_batch_video_dir_avoids_same_filename_collision(self):
        self.assertNotEqual(
            build_batch_video_dir("/tmp/videos/a/sample.mp4", "timelines"),
            build_batch_video_dir("/tmp/videos/b/sample.mp4", "timelines"),
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
                tags=["chatgpt", "planning"],
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
        scene_boundaries = [SceneBoundary(time_seconds=8.0, score=0.55)]

        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "timeline.json"
            transcript_path = Path(directory) / "transcript.json"
            transcript_path.write_text(
                json.dumps(
                    [
                        {
                            "start_seconds": 1.0,
                            "end_seconds": 3.5,
                            "text": "仕様を確認しています",
                            "speaker": "user",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with (
                patch("video_timeline.cli.load_video_metadata", return_value=video) as load_video,
                patch("video_timeline.cli.safe_detect_scene_boundaries", return_value=scene_boundaries) as detect_scenes,
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
                            "--vl-model",
                            "custom-vl:latest",
                            "--transcript-json",
                            str(transcript_path),
                        ]
                    )

            saved = json.loads(output_path.read_text(encoding="utf-8"))
            output = stdout.getvalue()

        self.assertEqual(exit_code, 0)
        load_video.assert_called_once_with("input.mp4")
        detect_scenes.assert_called_once_with(video.path, progress=ANY)
        extract.assert_called_once_with(
            video,
            frames_dir=build_run_frames_dir(video.path, "custom_frames"),
            interval_seconds=5.0,
            progress=ANY,
        )
        summarize.assert_called_once_with(frames, model="custom-vl:latest", progress=ANY)
        build_timeline.assert_called_once_with(summaries, video)
        detect_events.assert_called_once_with(timeline)
        self.assertIn("動画メタデータ取得中", output)
        self.assertIn("音声文字起こし読み込み中", output)
        self.assertIn("フレーム抽出中", output)
        self.assertIn("フレーム要約中", output)
        self.assertIn("タイムライン生成中", output)
        self.assertIn("イベント生成中", output)
        self.assertIn("JSON保存中", output)
        self.assertIn(f"wrote {output_path}", output)
        self.assertEqual(saved["video"]["path"], "/tmp/input.mp4")
        self.assertEqual(saved["analysis"]["interval_seconds"], 5.0)
        self.assertEqual(saved["analysis"]["vl_provider"], "ollama")
        self.assertEqual(saved["analysis"]["vl_model"], "custom-vl:latest")
        self.assertEqual(
            saved["storage"],
            {
                "video_path": "/tmp/input.mp4",
                "frames_dir": str(build_run_frames_dir(video.path, "custom_frames")),
                "timeline_path": str(output_path),
            },
        )
        self.assertEqual(saved["frame_summaries"][0]["summary"], "ChatGPTで仕様相談をしている")
        self.assertEqual(
            saved["scene_boundaries"],
            [{"time_seconds": 8.0, "source": "ffmpeg_scene", "score": 0.55}],
        )
        self.assertEqual(
            saved["transcripts"],
            [
                {
                    "start_seconds": 1.0,
                    "end_seconds": 3.5,
                    "text": "仕様を確認しています",
                    "source": "external_asr",
                    "speaker": "user",
                }
            ],
        )
        self.assertEqual(
            saved["timeline"],
            [
                {
                    "start_seconds": 0.0,
                    "end_seconds": 12.5,
                    "summary": "ChatGPTで仕様相談をしている",
                    "frame_indices": [0],
                    "tags": ["chatgpt", "planning"],
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

    def test_cli_resolves_simple_video_run_paths_with_app_config(self):
        config = AppConfig(storage=StoragePathConfig(storage_root=Path("/mnt/video-timeline")))

        with (
            patch("video_timeline.cli.load_app_config", return_value=config),
            patch("video_timeline.cli.run_video", return_value=Path("/mnt/video-timeline/timelines/timeline-sample1.json")) as run_video,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(["sample1.mp4", "--output", "timeline-sample1.json"])

        self.assertEqual(exit_code, 0)
        run_video.assert_called_once_with(
            Path("/mnt/video-timeline/videos/sample1.mp4"),
            Path("/mnt/video-timeline/timelines/timeline-sample1.json"),
            Path("/mnt/video-timeline/frames"),
            10,
            vl_model="gemma3:12b",
            transcript_json=None,
        )
        self.assertIn("wrote /mnt/video-timeline/timelines/timeline-sample1.json", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_cli_uses_video_stem_output_with_app_config_when_output_is_omitted(self):
        config = AppConfig(storage=StoragePathConfig(storage_root=Path("/mnt/video-timeline")))

        with (
            patch("video_timeline.cli.load_app_config", return_value=config),
            patch("video_timeline.cli.run_video", return_value=Path("/mnt/video-timeline/timelines/sample1.json")) as run_video,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(["sample1.mp4"])

        self.assertEqual(exit_code, 0)
        run_video.assert_called_once_with(
            Path("/mnt/video-timeline/videos/sample1.mp4"),
            Path("/mnt/video-timeline/timelines/sample1.json"),
            Path("/mnt/video-timeline/frames"),
            10,
            vl_model="gemma3:12b",
            transcript_json=None,
        )
        self.assertIn("wrote /mnt/video-timeline/timelines/sample1.json", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_clip_cli_connects_timeline_json_to_video_clipper(self):
        with (
            patch("video_timeline.cli.load_app_config", return_value=None),
            patch("video_timeline.cli.clip_timeline_entry", return_value=Path("clip.mp4")) as clip,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(
                [
                    "clip",
                    "timeline.json",
                    "--index",
                    "3",
                    "--output",
                    "clip.mp4",
                    "--padding-seconds",
                    "1.5",
                    "--accurate",
                    "--crf",
                    "20",
                    "--preset",
                    "fast",
                ]
            )

        self.assertEqual(exit_code, 0)
        clip.assert_called_once_with(
            "timeline.json",
            index=3,
            output_path="clip.mp4",
            padding_seconds=1.5,
            accurate=True,
            crf=20,
            preset="fast",
        )
        self.assertIn("wrote clip.mp4", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_clip_cli_resolves_simple_timeline_and_output_with_app_config(self):
        config = AppConfig(storage=StoragePathConfig(storage_root=Path("/mnt/video-timeline")))

        with (
            patch("video_timeline.cli.load_app_config", return_value=config),
            patch("video_timeline.cli.clip_timeline_entry", return_value=Path("/mnt/video-timeline/clips/clip1.mp4")) as clip,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(["clip", "sample1.json", "--index", "3", "--output", "clip1.mp4"])

        self.assertEqual(exit_code, 0)
        clip.assert_called_once_with(
            Path("/mnt/video-timeline/timelines/sample1.json"),
            index=3,
            output_path=Path("/mnt/video-timeline/clips/clip1.mp4"),
            padding_seconds=0.0,
            accurate=False,
            crf=None,
            preset=None,
        )
        self.assertIn("wrote /mnt/video-timeline/clips/clip1.mp4", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_clip_cli_allows_omitted_output_for_storage_timeline(self):
        with (
            patch("video_timeline.cli.load_app_config", return_value=None),
            patch("video_timeline.cli.clip_timeline_entry", return_value=Path("/mnt/video-timeline/clips/timeline_000003.mp4")) as clip,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(["clip", "timeline.json", "--index", "3"])

        self.assertEqual(exit_code, 0)
        clip.assert_called_once_with(
            "timeline.json",
            index=3,
            output_path=None,
            padding_seconds=0.0,
            accurate=False,
            crf=None,
            preset=None,
        )
        self.assertIn("wrote /mnt/video-timeline/clips/timeline_000003.mp4", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_clip_cli_connects_index_range_to_video_clipper(self):
        with (
            patch("video_timeline.cli.load_app_config", return_value=None),
            patch(
                "video_timeline.cli.clip_timeline_entry_range",
                return_value=[Path("clips/timeline_000003.mp4"), Path("clips/timeline_000004.mp4")],
            ) as clip_range,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(
                [
                    "clip",
                    "timeline.json",
                    "--start-index",
                    "3",
                    "--end-index",
                    "4",
                    "--output",
                    "clips",
                    "--padding-seconds",
                    "1.5",
                    "--accurate",
                    "--crf",
                    "20",
                    "--preset",
                    "fast",
                ]
            )

        self.assertEqual(exit_code, 0)
        clip_range.assert_called_once_with(
            "timeline.json",
            start_index=3,
            end_index=4,
            output_dir="clips",
            padding_seconds=1.5,
            accurate=True,
            crf=20,
            preset="fast",
        )
        self.assertIn("wrote clips/timeline_000003.mp4", stdout.getvalue())
        self.assertIn("wrote clips/timeline_000004.mp4", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_clip_cli_connects_tag_to_video_clipper(self):
        with (
            patch("video_timeline.cli.load_app_config", return_value=None),
            patch(
                "video_timeline.cli.clip_timeline_entries_by_tag",
                return_value=[Path("clips/timeline_000003.mp4"), Path("clips/timeline_000004.mp4")],
            ) as clip_by_tag,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(
                [
                    "clip",
                    "timeline.json",
                    "--tag",
                    "github",
                    "--output",
                    "clips",
                    "--padding-seconds",
                    "1.5",
                ]
            )

        self.assertEqual(exit_code, 0)
        clip_by_tag.assert_called_once_with(
            "timeline.json",
            tag="github",
            output_dir="clips",
            padding_seconds=1.5,
            accurate=False,
            crf=None,
            preset=None,
        )
        self.assertIn("wrote clips/timeline_000003.mp4", stdout.getvalue())
        self.assertIn("wrote clips/timeline_000004.mp4", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_clip_cli_prints_no_matches_for_empty_tag_clip_result(self):
        with (
            patch("video_timeline.cli.load_app_config", return_value=None),
            patch("video_timeline.cli.clip_timeline_entries_by_tag", return_value=[]),
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(["clip", "timeline.json", "--tag", "github", "--output", "clips"])

        self.assertEqual(exit_code, 0)
        self.assertIn("no matches", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_clip_cli_rejects_mixed_clip_selection_modes(self):
        with (
            patch("video_timeline.cli.clip_timeline_entry") as clip,
            patch("video_timeline.cli.clip_timeline_entry_range") as clip_range,
            patch("video_timeline.cli.clip_timeline_entries_by_tag") as clip_by_tag,
            patch("sys.stdout", new_callable=io.StringIO),
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(
                [
                    "clip",
                    "timeline.json",
                    "--index",
                    "3",
                    "--start-index",
                    "3",
                    "--end-index",
                    "4",
                    "--tag",
                    "github",
                    "--output",
                    "clips",
                ]
            )

        self.assertEqual(exit_code, 1)
        clip.assert_not_called()
        clip_range.assert_not_called()
        clip_by_tag.assert_not_called()
        self.assertIn("同時に指定できません", stderr.getvalue())

    def test_clip_cli_rejects_missing_index_selection(self):
        with (
            patch("video_timeline.cli.clip_timeline_entry") as clip,
            patch("video_timeline.cli.clip_timeline_entry_range") as clip_range,
            patch("sys.stdout", new_callable=io.StringIO),
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(["clip", "timeline.json", "--output", "clips"])

        self.assertEqual(exit_code, 1)
        clip.assert_not_called()
        clip_range.assert_not_called()
        self.assertIn("--index、--start-index/--end-index、--tagのいずれか", stderr.getvalue())

    def test_clip_cli_returns_error_for_video_clipper_failure(self):
        with (
            patch("video_timeline.cli.load_app_config", return_value=None),
            patch("video_timeline.cli.clip_timeline_entry", side_effect=ValueError("failed")),
            patch("sys.stdout", new_callable=io.StringIO),
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(["clip", "timeline.json", "--index", "3", "--output", "clip.mp4"])

        self.assertEqual(exit_code, 1)
        self.assertIn("error: failed", stderr.getvalue())

    def test_search_cli_prints_matching_timeline_lines(self):
        with (
            patch("video_timeline.cli.run_search", return_value=["3  01:20-04:10  ChatGPTで仕様相談"]) as search,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(["search", "timeline.json", "chatgpt"])

        self.assertEqual(exit_code, 0)
        search.assert_called_once()
        args = search.call_args.args[0]
        self.assertEqual(args.timeline_json, "timeline.json")
        self.assertEqual(args.query, "chatgpt")
        self.assertIn("3  01:20-04:10  ChatGPTで仕様相談", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_search_cli_prints_no_matches_for_empty_result(self):
        with (
            patch("video_timeline.cli.run_search", return_value=[]),
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(["search", "timeline.json", "missing"])

        self.assertEqual(exit_code, 0)
        self.assertIn("no matches", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_search_cli_resolves_simple_timeline_with_app_config(self):
        config = AppConfig(storage=StoragePathConfig(storage_root=Path("/mnt/video-timeline")))

        with (
            patch("video_timeline.cli.load_app_config", return_value=config),
            patch("video_timeline.cli.search_timeline_file", return_value=[]) as search,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(["search", "sample1.json", "chatgpt"])

        self.assertEqual(exit_code, 0)
        search.assert_called_once_with(Path("/mnt/video-timeline/timelines/sample1.json"), "chatgpt")
        self.assertIn("no matches", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_search_cli_returns_error_for_search_failure(self):
        with (
            patch("video_timeline.cli.run_search", side_effect=ValueError("failed")),
            patch("sys.stdout", new_callable=io.StringIO),
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(["search", "timeline.json", "chatgpt"])

        self.assertEqual(exit_code, 1)
        self.assertIn("error: failed", stderr.getvalue())

    def test_export_html_cli_connects_timeline_json_to_exporter(self):
        with (
            patch("video_timeline.cli.load_app_config", return_value=None),
            patch("video_timeline.cli.export_timeline_html_file", return_value=Path("timeline.html")) as export_html,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(["export-html", "timeline.json", "--output", "timeline.html"])

        self.assertEqual(exit_code, 0)
        export_html.assert_called_once_with("timeline.json", "timeline.html")
        self.assertIn("wrote timeline.html", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_export_html_cli_resolves_basename_with_storage_config(self):
        config = AppConfig(storage=StoragePathConfig(storage_root=Path("/mnt/video-timeline")))

        with (
            patch("video_timeline.cli.load_app_config", return_value=config),
            patch(
                "video_timeline.cli.export_timeline_html_file",
                return_value=Path("/mnt/video-timeline/html/timeline.html"),
            ) as export_html,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(["export-html", "timeline"])

        self.assertEqual(exit_code, 0)
        export_html.assert_called_once_with(
            Path("/mnt/video-timeline/timelines/timeline.json"),
            Path("/mnt/video-timeline/html/timeline.html"),
        )
        self.assertIn("wrote /mnt/video-timeline/html/timeline.html", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_export_html_cli_requires_output_without_storage_config(self):
        with (
            patch("video_timeline.cli.load_app_config", return_value=None),
            patch("sys.stdout", new_callable=io.StringIO),
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(["export-html", "timeline.json"])

        self.assertEqual(exit_code, 1)
        self.assertIn("error: --outputが必要です", stderr.getvalue())

    def test_export_html_cli_returns_error_for_export_failure(self):
        with (
            patch("video_timeline.cli.export_timeline_html_file", side_effect=ValueError("failed")),
            patch("sys.stdout", new_callable=io.StringIO),
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(["export-html", "timeline.json", "--output", "timeline.html"])

        self.assertEqual(exit_code, 1)
        self.assertIn("error: failed", stderr.getvalue())

    def test_batch_cli_processes_all_mp4s_and_reports_counts(self):
        first = Path("/tmp/videos/a/sample.mp4")
        second = Path("/tmp/videos/b/sample.mp4")

        with (
            patch("video_timeline.cli.load_app_config", return_value=None),
            patch("video_timeline.cli.discover_mp4_files", return_value=[first, second]) as discover,
            patch(
                "video_timeline.cli.run_video",
                side_effect=lambda _input, output, *_args, **_kwargs: Path(output),
            ) as run_video,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(
                [
                    "--input-dir",
                    "/tmp/videos",
                    "--output-dir",
                    "timelines",
                    "--interval-seconds",
                    "5",
                    "--vl-model",
                    "custom-vl:latest",
                ]
            )

        self.assertEqual(exit_code, 0)
        discover.assert_called_once_with("/tmp/videos")
        self.assertEqual(run_video.call_count, 2)
        run_video.assert_any_call(
            first,
            build_batch_video_dir(first, "timelines") / "timeline.json",
            build_batch_video_dir(first, "timelines") / "frames",
            5.0,
            isolate_frames=False,
            vl_model="custom-vl:latest",
            transcript_json=None,
        )
        run_video.assert_any_call(
            second,
            build_batch_video_dir(second, "timelines") / "timeline.json",
            build_batch_video_dir(second, "timelines") / "frames",
            5.0,
            isolate_frames=False,
            vl_model="custom-vl:latest",
            transcript_json=None,
        )
        self.assertIn("batch complete: success=2 failure=0", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_batch_cli_uses_storage_dirs_with_app_config(self):
        config = AppConfig(storage=StoragePathConfig(storage_root=Path("/mnt/video-timeline")))
        first = Path("/mnt/video-timeline/videos/a/sample.mp4")

        with (
            patch("video_timeline.cli.load_app_config", return_value=config),
            patch("video_timeline.cli.discover_mp4_files", return_value=[first]) as discover,
            patch(
                "video_timeline.cli.run_video",
                side_effect=lambda _input, output, *_args, **_kwargs: Path(output),
            ) as run_video,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(["--batch"])

        self.assertEqual(exit_code, 0)
        discover.assert_called_once_with(Path("/mnt/video-timeline/videos"))
        run_video.assert_called_once_with(
            first,
            build_batch_video_dir(first, Path("/mnt/video-timeline/timelines")) / "timeline.json",
            build_batch_video_dir(first, Path("/mnt/video-timeline/timelines")) / "frames",
            10.0,
            isolate_frames=False,
            vl_model="gemma3:12b",
            transcript_json=None,
        )
        self.assertIn("batch complete: success=1 failure=0", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_batch_cli_requires_config_or_input_dir(self):
        with (
            patch("video_timeline.cli.load_app_config", return_value=None),
            patch("sys.stdout", new_callable=io.StringIO),
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(["--batch"])

        self.assertEqual(exit_code, 1)
        self.assertIn("error: --batchを使う場合はvideo_timeline.tomlまたは--input-dirが必要です", stderr.getvalue())

    def test_batch_cli_requires_output_dir_without_app_config(self):
        with (
            patch("video_timeline.cli.load_app_config", return_value=None),
            patch("sys.stdout", new_callable=io.StringIO),
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(["--input-dir", "videos"])

        self.assertEqual(exit_code, 1)
        self.assertIn("error: --batchまたは--input-dirを使う場合は--output-dirが必要です", stderr.getvalue())

    def test_batch_cli_rejects_transcript_json(self):
        with (
            patch("video_timeline.cli.load_app_config", return_value=None),
            patch("video_timeline.cli.run_video") as run_video,
            patch("sys.stdout", new_callable=io.StringIO),
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(["--batch", "--input-dir", "videos", "--output-dir", "timelines", "--transcript-json", "transcript.json"])

        self.assertEqual(exit_code, 1)
        run_video.assert_not_called()
        self.assertIn("--transcript-jsonはbatch CLIでは指定できません", stderr.getvalue())

    def test_batch_cli_continues_after_single_video_failure(self):
        first = Path("/tmp/videos/a/sample.mp4")
        second = Path("/tmp/videos/b/sample.mp4")

        def run_video_side_effect(input_path, output_path, *_args, **_kwargs):
            if input_path == first:
                raise ValueError("failed")
            return Path(output_path)

        with (
            patch("video_timeline.cli.load_app_config", return_value=None),
            patch("video_timeline.cli.discover_mp4_files", return_value=[first, second]),
            patch("video_timeline.cli.run_video", side_effect=run_video_side_effect) as run_video,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            exit_code = main(["--input-dir", "/tmp/videos", "--output-dir", "timelines"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(run_video.call_count, 2)
        self.assertIn("batch complete: success=1 failure=1", stdout.getvalue())
        self.assertIn("batch video failed: /tmp/videos/a/sample.mp4: failed", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
