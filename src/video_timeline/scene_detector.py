from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess


DEFAULT_SCENE_THRESHOLD = 0.4
SCENE_DETECTOR_SOURCE = "ffmpeg_scene"


class SceneDetectorError(ValueError):
    pass


@dataclass(frozen=True)
class SceneBoundary:
    time_seconds: float
    score: float | None = None
    source: str = SCENE_DETECTOR_SOURCE

    def to_dict(self) -> dict[str, float | str]:
        payload: dict[str, float | str] = {
            "time_seconds": self.time_seconds,
            "source": self.source,
        }
        if self.score is not None:
            payload["score"] = self.score
        return payload


def detect_scene_boundaries(
    video_path: str | Path,
    threshold: float = DEFAULT_SCENE_THRESHOLD,
) -> list[SceneBoundary]:
    if threshold < 0.0 or threshold > 1.0:
        raise SceneDetectorError("scene thresholdは0.0から1.0の範囲で指定してください。")

    command = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(video_path),
        "-vf",
        f"select='gt(scene,{threshold:g})',metadata=print",
        "-f",
        "null",
        "-",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=True)
    except FileNotFoundError as exc:
        raise SceneDetectorError("ffmpegが見つかりません。") from exc
    except subprocess.CalledProcessError as exc:
        raise SceneDetectorError(f"scene boundaryを検出できません: {video_path}") from exc

    return parse_ffmpeg_scene_metadata(f"{completed.stdout}\n{completed.stderr}")


def safe_detect_scene_boundaries(
    video_path: str | Path,
    threshold: float = DEFAULT_SCENE_THRESHOLD,
) -> list[SceneBoundary]:
    try:
        return detect_scene_boundaries(video_path, threshold=threshold)
    except SceneDetectorError:
        return []


def parse_ffmpeg_scene_metadata(output: str) -> list[SceneBoundary]:
    boundaries: list[SceneBoundary] = []
    pending_time: float | None = None
    pending_score: float | None = None

    for line in output.splitlines():
        time_match = re.search(r"pts_time:([0-9]+(?:\.[0-9]+)?)", line)
        if time_match:
            if pending_time is not None:
                boundaries.append(SceneBoundary(time_seconds=pending_time, score=pending_score))
            pending_time = float(time_match.group(1))
            pending_score = None
            continue

        score_match = re.search(r"lavfi\.scene_score=([0-9]+(?:\.[0-9]+)?)", line)
        if score_match and pending_time is not None:
            pending_score = float(score_match.group(1))

    if pending_time is not None:
        boundaries.append(SceneBoundary(time_seconds=pending_time, score=pending_score))

    return _deduplicate_boundaries(boundaries)


def _deduplicate_boundaries(boundaries: list[SceneBoundary]) -> list[SceneBoundary]:
    deduplicated: list[SceneBoundary] = []
    seen_times: set[float] = set()
    for boundary in sorted(boundaries, key=lambda item: item.time_seconds):
        rounded_time = round(boundary.time_seconds, 3)
        if rounded_time in seen_times:
            continue
        seen_times.add(rounded_time)
        deduplicated.append(boundary)
    return deduplicated
