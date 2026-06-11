from __future__ import annotations

from dataclasses import dataclass

from .frame_summarizer import FrameSummary
from .video_loader import VideoMetadata


@dataclass(frozen=True)
class TimelineEntry:
    start_seconds: float
    end_seconds: float
    summary: str
    frame_indices: list[int]

    def to_dict(self) -> dict[str, float | str | list[int]]:
        return {
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "summary": self.summary,
            "frame_indices": self.frame_indices,
        }


def build_timeline(frame_summaries: list[FrameSummary], video: VideoMetadata) -> list[TimelineEntry]:
    sorted_summaries = sorted(frame_summaries, key=lambda item: (item.time_seconds, item.index))
    if not sorted_summaries:
        return []

    entries: list[TimelineEntry] = []
    current_summary = _normalize_summary(sorted_summaries[0].summary)
    current_start = sorted_summaries[0].time_seconds
    current_frame_indices = [sorted_summaries[0].index]
    current_display_summary = sorted_summaries[0].summary.strip()

    for summary in sorted_summaries[1:]:
        normalized_summary = _normalize_summary(summary.summary)
        if normalized_summary == current_summary:
            current_frame_indices.append(summary.index)
            continue

        entries.append(
            TimelineEntry(
                start_seconds=current_start,
                end_seconds=summary.time_seconds,
                summary=current_display_summary,
                frame_indices=current_frame_indices,
            )
        )
        current_summary = normalized_summary
        current_start = summary.time_seconds
        current_frame_indices = [summary.index]
        current_display_summary = summary.summary.strip()

    entries.append(
        TimelineEntry(
            start_seconds=current_start,
            end_seconds=video.duration_seconds,
            summary=current_display_summary,
            frame_indices=current_frame_indices,
        )
    )
    return entries


def _normalize_summary(summary: str) -> str:
    return " ".join(summary.strip().split())
