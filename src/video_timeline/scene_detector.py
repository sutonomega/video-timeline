from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
from typing import Callable


DEFAULT_SCENE_THRESHOLD = 0.4
SCENE_DETECTOR_SOURCE = "ffmpeg_scene"
SceneDetectionProgress = Callable[[float], None]


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
    progress: SceneDetectionProgress | None = None,
) -> list[SceneBoundary]:
    if threshold < 0.0 or threshold > 1.0:
        raise SceneDetectorError("scene thresholdは0.0から1.0の範囲で指定してください。")

    command = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-progress",
        "pipe:1",
        "-i",
        str(video_path),
        "-vf",
        "select='gte(scene,0)',metadata=print",
        "-f",
        "null",
        "-",
    ]
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SceneDetectorError("ffmpegが見つかりません。") from exc

    metadata_parser = SceneMetadataParser(threshold=threshold)
    if process.stdout is not None:
        for line in process.stdout:
            metadata_parser.feed_line(line)
            processed_seconds = parse_ffmpeg_progress_time(line)
            if progress is not None and processed_seconds is not None:
                progress(processed_seconds)

    return_code = process.wait()
    if return_code != 0:
        raise SceneDetectorError(f"scene boundaryを検出できません: {video_path}")

    return metadata_parser.boundaries()


def safe_detect_scene_boundaries(
    video_path: str | Path,
    threshold: float = DEFAULT_SCENE_THRESHOLD,
    progress: SceneDetectionProgress | None = None,
) -> list[SceneBoundary]:
    try:
        return detect_scene_boundaries(video_path, threshold=threshold, progress=progress)
    except SceneDetectorError:
        return []


class SceneMetadataParser:
    def __init__(self, threshold: float = 0.0) -> None:
        self.threshold = threshold
        self.pending_time: float | None = None
        self.boundary_candidates: list[SceneBoundary] = []

    def feed_line(self, line: str) -> None:
        time_match = re.search(r"pts_time:([0-9]+(?:\.[0-9]+)?)", line)
        if time_match:
            self.pending_time = float(time_match.group(1))
            return

        score_match = re.search(r"lavfi\.scene_score=([0-9]+(?:\.[0-9]+)?)", line)
        if score_match and self.pending_time is not None:
            score = float(score_match.group(1))
            if score >= self.threshold:
                self.boundary_candidates.append(SceneBoundary(time_seconds=self.pending_time, score=score))
            self.pending_time = None

    def boundaries(self) -> list[SceneBoundary]:
        return _deduplicate_boundaries(self.boundary_candidates)


def parse_ffmpeg_scene_metadata(output: str, threshold: float = 0.0) -> list[SceneBoundary]:
    parser = SceneMetadataParser(threshold=threshold)
    for line in output.splitlines():
        parser.feed_line(line)
    return parser.boundaries()


def parse_ffmpeg_progress_time(line: str) -> float | None:
    progress_match = re.search(r"^out_time=([0-9]+):([0-9]+):([0-9]+(?:\.[0-9]+)?)$", line.strip())
    if not progress_match:
        return None

    hours = int(progress_match.group(1))
    minutes = int(progress_match.group(2))
    seconds = float(progress_match.group(3))
    return hours * 3600 + minutes * 60 + seconds


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
