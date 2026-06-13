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
    if not accurate and (crf is not None or preset is not None):
        raise VideoClipperError("--crf/--presetは--accurate指定時だけ使えます。")
    if accurate:
        actual_crf, actual_preset = _build_accurate_encoding_options(crf, preset)
    else:
        actual_crf = DEFAULT_ACCURATE_CRF
        actual_preset = DEFAULT_ACCURATE_PRESET

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
