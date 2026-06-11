from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess


SUPPORTED_EXTENSIONS = {".mp4"}


class VideoLoaderError(ValueError):
    pass


@dataclass(frozen=True)
class VideoMetadata:
    path: str
    duration_seconds: float
    fps: float
    frame_count: int
    width: int
    height: int

    def to_dict(self) -> dict[str, int | float | str]:
        return {
            "path": self.path,
            "duration_seconds": self.duration_seconds,
            "fps": self.fps,
            "frame_count": self.frame_count,
            "width": self.width,
            "height": self.height,
        }


def load_video_metadata(path: str | Path) -> VideoMetadata:
    video_path = Path(path)
    _validate_input_path(video_path)
    resolved_path = video_path.resolve()
    payload = _run_ffprobe(video_path)
    stream = _find_video_stream(payload)

    duration_seconds = _parse_duration(payload, stream)
    fps = _parse_fps(stream)
    frame_count = _parse_frame_count(stream, duration_seconds, fps)
    width = _parse_positive_int(stream.get("width"), "width")
    height = _parse_positive_int(stream.get("height"), "height")

    return VideoMetadata(
        path=str(resolved_path),
        duration_seconds=duration_seconds,
        fps=fps,
        frame_count=frame_count,
        width=width,
        height=height,
    )


def _validate_input_path(path: Path) -> None:
    if not path.exists():
        raise VideoLoaderError(f"動画ファイルが存在しません: {path}")
    if not path.is_file():
        raise VideoLoaderError(f"動画ファイルではありません: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise VideoLoaderError(f"未対応の動画形式です: {path.suffix or '(拡張子なし)'}。対応形式: {supported}")


def _run_ffprobe(path: Path) -> dict:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise VideoLoaderError("ffprobeが見つかりません。ffmpegをインストールしてください。") from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise VideoLoaderError(f"動画メタデータを取得できません: {message}") from exc

    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise VideoLoaderError("ffprobeの出力JSONを読み取れません。") from exc


def _find_video_stream(payload: dict) -> dict:
    streams = payload.get("streams")
    if not isinstance(streams, list):
        raise VideoLoaderError("ffprobeの出力にstreamsがありません。")
    for stream in streams:
        if isinstance(stream, dict) and stream.get("codec_type") == "video":
            return stream
    raise VideoLoaderError("動画ストリームが見つかりません。")


def _parse_duration(payload: dict, stream: dict) -> float:
    raw_duration = stream.get("duration") or payload.get("format", {}).get("duration")
    try:
        duration = float(raw_duration)
    except (TypeError, ValueError) as exc:
        raise VideoLoaderError("動画durationを取得できません。") from exc
    if duration <= 0:
        raise VideoLoaderError("動画durationが0以下です。")
    return duration


def _parse_fps(stream: dict) -> float:
    rate = stream.get("avg_frame_rate") or stream.get("r_frame_rate")
    if not isinstance(rate, str) or not rate:
        raise VideoLoaderError("動画fpsを取得できません。")
    if "/" in rate:
        numerator_text, denominator_text = rate.split("/", 1)
        try:
            numerator = float(numerator_text)
            denominator = float(denominator_text)
        except ValueError as exc:
            raise VideoLoaderError("動画fpsを取得できません。") from exc
        if denominator == 0:
            raise VideoLoaderError("動画fpsを取得できません。")
        fps = numerator / denominator
    else:
        try:
            fps = float(rate)
        except ValueError as exc:
            raise VideoLoaderError("動画fpsを取得できません。") from exc

    if fps <= 0:
        raise VideoLoaderError("動画fpsが0以下です。")
    return fps


def _parse_frame_count(stream: dict, duration_seconds: float, fps: float) -> int:
    raw_frame_count = stream.get("nb_frames")
    if raw_frame_count not in (None, "N/A"):
        return _parse_positive_int(raw_frame_count, "frame_count")
    return max(1, round(duration_seconds * fps))


def _parse_positive_int(value: object, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise VideoLoaderError(f"{field_name}を取得できません。") from exc
    if parsed <= 0:
        raise VideoLoaderError(f"{field_name}が0以下です。")
    return parsed
