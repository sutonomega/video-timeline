from __future__ import annotations

import json
from pathlib import Path
import subprocess


class VideoClipperError(ValueError):
    pass


DEFAULT_ACCURATE_CRF = 18
DEFAULT_ACCURATE_PRESET = "veryfast"
ALLOWED_ACCURATE_PRESETS = {
    "ultrafast",
    "superfast",
    "veryfast",
    "faster",
    "fast",
    "medium",
    "slow",
    "slower",
    "veryslow",
    "placebo",
}


def clip_timeline_entry(
    timeline_json_path: str | Path,
    index: int,
    output_path: str | Path,
    padding_seconds: float = 0.0,
    accurate: bool = False,
    crf: int | None = None,
    preset: str | None = None,
) -> Path:
    if index < 0:
        raise VideoClipperError("timeline indexは0以上で指定してください。")
    if padding_seconds < 0:
        raise VideoClipperError("--padding-secondsは0以上で指定してください。")
    actual_crf, actual_preset = _resolve_encoding_options(accurate, crf, preset)

    document = load_timeline_document(timeline_json_path)
    video_path = _read_video_path(document)
    timeline_entry = _read_timeline_entry(document, index)
    start_seconds, duration_seconds = _build_clip_range(timeline_entry, padding_seconds)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    _run_ffmpeg_clip(
        video_path,
        start_seconds,
        duration_seconds,
        output,
        accurate=accurate,
        crf=actual_crf,
        preset=actual_preset,
    )
    return output


def clip_timeline_entry_range(
    timeline_json_path: str | Path,
    start_index: int,
    end_index: int,
    output_dir: str | Path,
    padding_seconds: float = 0.0,
    accurate: bool = False,
    crf: int | None = None,
    preset: str | None = None,
) -> list[Path]:
    if start_index < 0 or end_index < 0:
        raise VideoClipperError("timeline indexは0以上で指定してください。")
    if end_index < start_index:
        raise VideoClipperError("--end-indexは--start-index以上で指定してください。")
    if padding_seconds < 0:
        raise VideoClipperError("--padding-secondsは0以上で指定してください。")
    document = load_timeline_document(timeline_json_path)
    _validate_timeline_range(document, start_index, end_index)

    return _clip_timeline_indices(
        document,
        indexes=range(start_index, end_index + 1),
        output_dir=output_dir,
        padding_seconds=padding_seconds,
        accurate=accurate,
        crf=crf,
        preset=preset,
    )


def clip_timeline_entries_by_tag(
    timeline_json_path: str | Path,
    tag: str,
    output_dir: str | Path,
    padding_seconds: float = 0.0,
    accurate: bool = False,
    crf: int | None = None,
    preset: str | None = None,
) -> list[Path]:
    normalized_tag = tag.casefold().strip()
    if not normalized_tag:
        raise VideoClipperError("--tagを指定してください。")
    if padding_seconds < 0:
        raise VideoClipperError("--padding-secondsは0以上で指定してください。")

    document = load_timeline_document(timeline_json_path)
    matched_indexes = _find_timeline_indexes_by_tag(document, normalized_tag)
    if not matched_indexes:
        return []

    return _clip_timeline_indices(
        document,
        indexes=matched_indexes,
        output_dir=output_dir,
        padding_seconds=padding_seconds,
        accurate=accurate,
        crf=crf,
        preset=preset,
    )


def _clip_timeline_indices(
    document: dict,
    indexes,
    output_dir: str | Path,
    padding_seconds: float,
    accurate: bool,
    crf: int | None,
    preset: str | None,
) -> list[Path]:
    actual_crf, actual_preset = _resolve_encoding_options(accurate, crf, preset)
    video_path = _read_video_path(document)
    output_directory = Path(output_dir)

    clip_ranges = []
    for index in indexes:
        timeline_entry = _read_timeline_entry(document, index)
        clip_ranges.append((index, *_build_clip_range(timeline_entry, padding_seconds)))

    outputs = []
    output_directory.mkdir(parents=True, exist_ok=True)
    for index, start_seconds, duration_seconds in clip_ranges:
        output = output_directory / _build_range_clip_filename(index)
        try:
            _run_ffmpeg_clip(
                video_path,
                start_seconds,
                duration_seconds,
                output,
                accurate=accurate,
                crf=actual_crf,
                preset=actual_preset,
            )
        except VideoClipperError as exc:
            raise VideoClipperError(f"timeline index {index} の切り出しに失敗しました: {exc}") from exc
        outputs.append(output)

    return outputs


def load_timeline_document(timeline_json_path: str | Path) -> dict:
    path = Path(timeline_json_path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise VideoClipperError(f"timeline JSONが存在しません: {path}") from exc
    except json.JSONDecodeError as exc:
        raise VideoClipperError(f"timeline JSONを読み取れません: {path}") from exc


def _read_video_path(document: dict) -> str:
    video = document.get("video")
    if not isinstance(video, dict):
        raise VideoClipperError("timeline JSONにvideoがありません。")
    video_path = video.get("path")
    if not isinstance(video_path, str) or not video_path:
        raise VideoClipperError("timeline JSONにvideo.pathがありません。")
    return video_path


def _read_timeline_entry(document: dict, index: int) -> dict:
    timeline = document.get("timeline")
    if not isinstance(timeline, list):
        raise VideoClipperError("timeline JSONにtimelineがありません。")
    try:
        entry = timeline[index]
    except IndexError as exc:
        raise VideoClipperError(f"timeline indexが存在しません: {index}") from exc
    if not isinstance(entry, dict):
        raise VideoClipperError(f"timeline entryが不正です: {index}")
    return entry


def _validate_timeline_range(document: dict, start_index: int, end_index: int) -> None:
    timeline = document.get("timeline")
    if not isinstance(timeline, list):
        raise VideoClipperError("timeline JSONにtimelineがありません。")
    if start_index >= len(timeline):
        raise VideoClipperError(f"timeline indexが存在しません: {start_index}")
    if end_index >= len(timeline):
        raise VideoClipperError(f"timeline indexが存在しません: {end_index}")


def _find_timeline_indexes_by_tag(document: dict, normalized_tag: str) -> list[int]:
    timeline = document.get("timeline")
    if not isinstance(timeline, list):
        raise VideoClipperError("timeline JSONにtimelineがありません。")

    events_by_timeline_index = _build_events_by_timeline_index(document)
    indexes = []
    for index, entry in enumerate(timeline):
        if not isinstance(entry, dict):
            raise VideoClipperError(f"timeline entryが不正です: {index}")
        if _timeline_entry_has_tag(entry, events_by_timeline_index.get(index, []), normalized_tag):
            indexes.append(index)
    return indexes


def _build_events_by_timeline_index(document: dict) -> dict[int, list[dict]]:
    events = document.get("events", [])
    if events is None:
        return {}
    if not isinstance(events, list):
        raise VideoClipperError("timeline JSONのeventsが不正です。")

    events_by_timeline_index: dict[int, list[dict]] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        timeline_index = event.get("timeline_index")
        if isinstance(timeline_index, int):
            events_by_timeline_index.setdefault(timeline_index, []).append(event)
    return events_by_timeline_index


def _timeline_entry_has_tag(entry: dict, events: list[dict], normalized_tag: str) -> bool:
    return _tags_include(entry.get("tags", []), normalized_tag) or any(
        _tags_include(event.get("tags", []), normalized_tag) for event in events
    )


def _tags_include(tags: object, normalized_tag: str) -> bool:
    return isinstance(tags, list) and any(isinstance(tag, str) and tag.casefold() == normalized_tag for tag in tags)


def _build_clip_range(timeline_entry: dict, padding_seconds: float) -> tuple[float, float]:
    start_seconds = timeline_entry.get("start_seconds")
    end_seconds = timeline_entry.get("end_seconds")
    if not isinstance(start_seconds, (int, float)) or not isinstance(end_seconds, (int, float)):
        raise VideoClipperError("timeline entryにstart_seconds/end_secondsがありません。")
    if end_seconds <= start_seconds:
        raise VideoClipperError("timeline entryの範囲が不正です。")

    padded_start = max(0.0, float(start_seconds) - padding_seconds)
    padded_end = float(end_seconds) + padding_seconds
    return padded_start, padded_end - padded_start


def _build_range_clip_filename(index: int) -> str:
    return f"timeline_{index:06d}.mp4"


def _resolve_encoding_options(accurate: bool, crf: int | None, preset: str | None) -> tuple[int, str]:
    if not accurate and (crf is not None or preset is not None):
        raise VideoClipperError("--crf/--presetは--accurate指定時だけ使えます。")
    if accurate:
        return _build_accurate_encoding_options(crf, preset)
    return DEFAULT_ACCURATE_CRF, DEFAULT_ACCURATE_PRESET


def _build_accurate_encoding_options(crf: int | None, preset: str | None) -> tuple[int, str]:
    actual_crf = DEFAULT_ACCURATE_CRF if crf is None else crf
    actual_preset = DEFAULT_ACCURATE_PRESET if preset is None else preset

    if actual_crf < 0 or actual_crf > 51:
        raise VideoClipperError("--crfは0から51の範囲で指定してください。")
    if actual_preset not in ALLOWED_ACCURATE_PRESETS:
        raise VideoClipperError("--presetに対応していない値が指定されました。")

    return actual_crf, actual_preset


def _run_ffmpeg_clip(
    video_path: str,
    start_seconds: float,
    duration_seconds: float,
    output_path: Path,
    accurate: bool = False,
    crf: int = DEFAULT_ACCURATE_CRF,
    preset: str = DEFAULT_ACCURATE_PRESET,
) -> None:
    if accurate:
        command = [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-ss",
            f"{start_seconds:g}",
            "-t",
            f"{duration_seconds:g}",
            "-c:v",
            "libx264",
            "-crf",
            str(crf),
            "-preset",
            preset,
            "-c:a",
            "aac",
            str(output_path),
        ]
    else:
        command = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start_seconds:g}",
            "-i",
            video_path,
            "-t",
            f"{duration_seconds:g}",
            "-c",
            "copy",
            str(output_path),
        ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise VideoClipperError("ffmpegが見つかりません。ffmpegをインストールしてください。") from exc
    except subprocess.CalledProcessError as exc:
        raise VideoClipperError(f"ffmpegによる動画切り出しに失敗しました: {exc.stderr}") from exc
