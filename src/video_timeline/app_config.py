from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
import tomllib


CONFIG_FILE_NAME = "video_timeline.toml"


@dataclass(frozen=True)
class StoragePathConfig:
    storage_root: Path
    videos_dir: str = "videos"
    frames_dir: str = "frames"
    timelines_dir: str = "timelines"
    clips_dir: str = "clips"
    html_dir: str = "html"

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> StoragePathConfig:
        storage_root = payload.get("root")
        if not isinstance(storage_root, str) or not storage_root.strip():
            raise ValueError("video_timeline.tomlにはstorage.rootが必要です")

        return cls(
            storage_root=Path(storage_root),
            videos_dir=_read_dir_name(payload, "videos_dir", "videos"),
            frames_dir=_read_dir_name(payload, "frames_dir", "frames"),
            timelines_dir=_read_dir_name(payload, "timelines_dir", "timelines"),
            clips_dir=_read_dir_name(payload, "clips_dir", "clips"),
            html_dir=_read_dir_name(payload, "html_dir", "html"),
        )

    def timeline_json_path(self, name: str) -> Path:
        path = Path(name)
        filename = path.name if path.suffix == ".json" else f"{path.name}.json"
        return self.storage_root / self.timelines_dir / filename

    def html_output_path(self, name: str) -> Path:
        path = Path(name)
        filename = f"{path.stem}.html" if path.suffix else f"{path.name}.html"
        return self.storage_root / self.html_dir / filename

    def video_file_path(self, filename: str | Path) -> Path:
        return self.storage_root / self.videos_dir / Path(filename).name

    def frames_directory_path(self) -> Path:
        return self.storage_root / self.frames_dir


@dataclass(frozen=True)
class AppConfig:
    storage: StoragePathConfig

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> AppConfig:
        storage = payload.get("storage")
        if not isinstance(storage, Mapping):
            raise ValueError("video_timeline.tomlには[storage]が必要です")

        return cls(storage=StoragePathConfig.from_mapping(storage))

    def timeline_json_path(self, name: str) -> Path:
        return self.storage.timeline_json_path(name)

    def html_output_path(self, name: str) -> Path:
        return self.storage.html_output_path(name)

    def video_file_path(self, filename: str | Path) -> Path:
        return self.storage.video_file_path(filename)

    def frames_directory_path(self) -> Path:
        return self.storage.frames_directory_path()


def _read_dir_name(payload: Mapping[str, object], key: str, default: str) -> str:
    value = payload.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"video_timeline.tomlの{key}は空ではない文字列にしてください")
    if Path(value).is_absolute():
        raise ValueError(f"video_timeline.tomlの{key}は相対パスにしてください")
    return value


def load_app_config(search_dirs: Sequence[Path] | None = None) -> AppConfig | None:
    for directory in search_dirs if search_dirs is not None else _default_config_dirs():
        config_path = directory / CONFIG_FILE_NAME
        if config_path.is_file():
            return load_app_config_file(config_path)
    return None


def load_app_config_file(path: str | Path) -> AppConfig:
    with Path(path).open("rb") as file:
        payload = tomllib.load(file)
    return AppConfig.from_mapping(payload)


def resolve_export_html_paths(
    timeline_json: str | Path,
    output_path: str | Path | None,
    config: AppConfig | None,
) -> tuple[str | Path, str | Path]:
    if output_path is not None:
        return timeline_json, output_path

    if config is None:
        raise ValueError("--outputが必要です")

    timeline_path = Path(timeline_json)
    if not _is_simple_filename(timeline_path):
        raise ValueError("--outputが必要です")

    name = timeline_path.stem if timeline_path.suffix == ".json" else timeline_path.name
    return config.timeline_json_path(name), config.html_output_path(name)


def resolve_video_run_paths(
    input_path: str | Path,
    output_path: str | Path | None,
    frames_dir: str | Path,
    config: AppConfig | None,
) -> tuple[str | Path, str | Path | None, str | Path]:
    if config is None:
        return input_path, output_path, frames_dir

    input_candidate = Path(input_path)
    if not _is_simple_filename(input_candidate):
        return input_path, output_path, frames_dir

    if output_path is not None:
        output_candidate = Path(output_path)
        if not _is_simple_filename(output_candidate):
            return input_path, output_path, frames_dir
        output_name = output_candidate
    else:
        output_name = input_candidate.stem

    resolved_frames_dir: str | Path = config.frames_directory_path() if Path(frames_dir) == Path("frames") else frames_dir
    return (
        config.video_file_path(input_candidate),
        config.timeline_json_path(output_name),
        resolved_frames_dir,
    )


def _default_config_dirs() -> list[Path]:
    directories: list[Path] = []
    current = Path.cwd().resolve(strict=False)
    while True:
        directories.append(current)
        if current.parent == current:
            return directories
        current = current.parent


def _is_simple_filename(path: Path) -> bool:
    return path.parent == Path(".") and path.name not in ("", ".", "..")
