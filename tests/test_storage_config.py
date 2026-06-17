from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_timeline.storage_config import (
    StoragePathConfig,
    load_storage_path_config,
    load_storage_path_config_file,
    resolve_export_html_paths,
)


class StorageConfigTest(unittest.TestCase):
    def test_load_storage_path_config_file_reads_shared_storage_dirs(self):
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

            config = load_storage_path_config_file(config_path)

        self.assertEqual(config.storage_root, Path("/mnt/video-timeline"))
        self.assertEqual(config.timelines_dir, "timelines")
        self.assertEqual(config.html_dir, "html")

    def test_load_storage_path_config_returns_none_without_config_file(self):
        with TemporaryDirectory() as directory:
            config = load_storage_path_config([Path(directory)])

        self.assertIsNone(config)

    def test_resolve_export_html_paths_uses_basename_with_config(self):
        config = StoragePathConfig(storage_root=Path("/mnt/video-timeline"))

        timeline_json, output_path = resolve_export_html_paths("sample1-gemma312b", None, config)

        self.assertEqual(timeline_json, Path("/mnt/video-timeline/timelines/sample1-gemma312b.json"))
        self.assertEqual(output_path, Path("/mnt/video-timeline/html/sample1-gemma312b.html"))

    def test_resolve_export_html_paths_accepts_json_basename_with_config(self):
        config = StoragePathConfig(storage_root=Path("/mnt/video-timeline"))

        timeline_json, output_path = resolve_export_html_paths("sample1-gemma312b.json", None, config)

        self.assertEqual(timeline_json, Path("/mnt/video-timeline/timelines/sample1-gemma312b.json"))
        self.assertEqual(output_path, Path("/mnt/video-timeline/html/sample1-gemma312b.html"))

    def test_resolve_export_html_paths_keeps_explicit_output(self):
        config = StoragePathConfig(storage_root=Path("/mnt/video-timeline"))

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
        config = StoragePathConfig(storage_root=Path("/mnt/video-timeline"))

        with self.assertRaisesRegex(ValueError, "--output"):
            resolve_export_html_paths("timelines/sample1.json", None, config)

    def test_load_storage_path_config_file_rejects_absolute_child_dir(self):
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / "video_timeline.toml"
            config_path.write_text(
                '[storage]\nroot = "/mnt/video-timeline"\nhtml_dir = "/tmp/html"\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "html_dir"):
                load_storage_path_config_file(config_path)

    def test_load_storage_path_config_file_requires_storage_table(self):
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / "video_timeline.toml"
            config_path.write_text('root = "/mnt/video-timeline"\n', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, r"\[storage\]"):
                load_storage_path_config_file(config_path)
