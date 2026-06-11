from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from .video_loader import VideoMetadata


DEFAULT_INTERVAL_SECONDS = 10.0


class FrameExtractorError(ValueError):
    pass


@dataclass(frozen=True)
class ExtractedFrame:
    index: int
    time_seconds: float
    image: str

    def to_dict(self) -> dict[str, float | int | str]:
        return {
            "index": self.index,
            "time_seconds": self.time_seconds,
            "image": self.image,
        }


def extract_frames(
    metadata: VideoMetadata,
    frames_dir: str | Path = "frames",
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
) -> list[ExtractedFrame]:
    if interval_seconds <= 0:
        raise FrameExtractorError("interval_secondsは0より大きい値を指定してください。")

    output_dir = Path(frames_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    frames: list[ExtractedFrame] = []
    for index, time_seconds in enumerate(generate_frame_times(metadata.duration_seconds, interval_seconds)):
        image_path = output_dir / format_frame_filename(time_seconds)
        _run_ffmpeg_extract_frame(metadata.path, time_seconds, image_path)
        frames.append(
            ExtractedFrame(
                index=index,
                time_seconds=time_seconds,
                image=str(image_path),
            )
        )
    return frames


def generate_frame_times(duration_seconds: float, interval_seconds: float = DEFAULT_INTERVAL_SECONDS) -> list[float]:
    if duration_seconds <= 0:
        raise FrameExtractorError("duration_secondsは0より大きい値を指定してください。")
    if interval_seconds <= 0:
        raise FrameExtractorError("interval_secondsは0より大きい値を指定してください。")

    times: list[float] = []
    current = 0.0
    while current < duration_seconds:
        times.append(round(current, 6))
        current += interval_seconds
    return times


def format_frame_filename(time_seconds: float) -> str:
    if time_seconds < 0:
        raise FrameExtractorError("time_secondsは0以上の値を指定してください。")
    return f"{int(time_seconds * 1000):09d}.jpg"


def _run_ffmpeg_extract_frame(video_path: str, time_seconds: float, image_path: Path) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{time_seconds:.6f}",
        "-i",
        video_path,
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(image_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise FrameExtractorError("ffmpegが見つかりません。ffmpegをインストールしてください。") from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise FrameExtractorError(f"フレームを抽出できません: {message}") from exc
