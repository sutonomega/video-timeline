from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_timeline.app_config import (
    AppConfig,
    StoragePathConfig,
    load_app_config,
    load_app_config_file,
    resolve_export_html_paths,
)


class AppConfigTest(unittest.TestCase):
    def test_load_app_config_file_reads_shared_storage_dirs(self):
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / "video_timeline.toml"
            config_path.write_text(
                '\n'.join(
                    [
                        "[storage]",
                        'root = "/mnt/video-timeline"',
                        'videos_dir = "videos"',
                        'frames_dir = "frames"',
                        'timelines_dir = "timelines"',
                        'clips_dir = "clips"',
                        'html_dir = "html"',
                    ]
                ),
                encoding="utf-8",
            )

            config = load_app_config_file(config_path)

        self.assertIsInstance(config, AppConfig)
        self.assertEqual(config.storage.storage_root, Path("/mnt/video-timeline"))
        self.assertEqual(config.storage.timelines_dir, "timelines")
        self.assertEqual(config.storage.html_dir, "html")

    def test_load_app_config_returns_none_without_config_file(self):
        with TemporaryDirectory() as directory:
            config = load_app_config([Path(directory)])

        self.assertIsNone(config)

    def test_load_app_config_searches_parent_directories(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            child = root / "project" / "subdir"
            child.mkdir(parents=True)
            config_path = root / "video_timeline.toml"
            config_path.write_text('[storage]\nroot = "/mnt/video-timeline"\n', encoding="utf-8")

            with patch("video_timeline.app_config.Path.cwd", return_value=child):
                config = load_app_config()

        self.assertIsNotNone(config)
        assert config is not None
        self.assertEqual(config.storage.storage_root, Path("/mnt/video-timeline"))

    def test_app_config_exposes_common_storage_paths(self):
        config = AppConfig(storage=StoragePathConfig(storage_root=Path("/mnt/video-timeline")))

        self.assertEqual(config.timeline_json_path("sample1"), Path("/mnt/video-timeline/timelines/sample1.json"))
        self.assertEqual(config.html_output_path("sample1"), Path("/mnt/video-timeline/html/sample1.html"))

    def test_resolve_export_html_paths_uses_basename_with_config(self):
        config = AppConfig(storage=StoragePathConfig(storage_root=Path("/mnt/video-timeline")))

        timeline_json, output_path = resolve_export_html_paths("timeline", None, config)

        self.assertEqual(timeline_json, Path("/mnt/video-timeline/timelines/timeline.json"))
        self.assertEqual(output_path, Path("/mnt/video-timeline/html/timeline.html"))

    def test_resolve_export_html_paths_accepts_json_basename_with_config(self):
        config = AppConfig(storage=StoragePathConfig(storage_root=Path("/mnt/video-timeline")))

        timeline_json, output_path = resolve_export_html_paths("timeline.json", None, config)

        self.assertEqual(timeline_json, Path("/mnt/video-timeline/timelines/timeline.json"))
        self.assertEqual(output_path, Path("/mnt/video-timeline/html/timeline.html"))

    def test_resolve_export_html_paths_keeps_explicit_output(self):
        config = AppConfig(storage=StoragePathConfig(storage_root=Path("/mnt/video-timeline")))

        timeline_json, output_path = resolve_export_html_paths(
            "/tmp/timeline.json",
            "/tmp/timeline.html",
            config,
        )

        self.assertEqual(timeline_json, "/tmp/timeline.json")
        self.assertEqual(output_path, "/tmp/timeline.html")

    def test_resolve_export_html_paths_requires_output_without_config(self):
        with self.assertRaisesRegex(ValueError, "--output"):
            resolve_export_html_paths("timeline.json", None, None)

    def test_resolve_export_html_paths_requires_output_for_path_input(self):
        config = AppConfig(storage=StoragePathConfig(storage_root=Path("/mnt/video-timeline")))

        with self.assertRaisesRegex(ValueError, "--output"):
            resolve_export_html_paths("timelines/sample1.json", None, config)

    def test_load_app_config_file_rejects_absolute_child_dir(self):
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / "video_timeline.toml"
            config_path.write_text(
                '[storage]\nroot = "/mnt/video-timeline"\nhtml_dir = "/tmp/html"\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "html_dir"):
                load_app_config_file(config_path)

    def test_load_app_config_file_requires_storage_table(self):
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / "video_timeline.toml"
            config_path.write_text('root = "/mnt/video-timeline"\n', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, r"\[storage\]"):
                load_app_config_file(config_path)
