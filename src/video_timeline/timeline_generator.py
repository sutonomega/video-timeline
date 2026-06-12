from __future__ import annotations

from dataclasses import dataclass
import re

from .frame_summarizer import FrameSummary
from .video_loader import VideoMetadata


SUMMARY_SIMILARITY_THRESHOLD = 0.6
TAG_SIMILARITY_THRESHOLD = 0.5


@dataclass(frozen=True)
class TimelineEntry:
    start_seconds: float
    end_seconds: float
    summary: str
    frame_indices: list[int]
    tags: list[str]

    def to_dict(self) -> dict[str, float | str | list[int] | list[str]]:
        return {
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "summary": self.summary,
            "frame_indices": self.frame_indices,
            "tags": self.tags,
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
    current_tags = list(sorted_summaries[0].tags)

    for summary in sorted_summaries[1:]:
        normalized_summary = _normalize_summary(summary.summary)
        if are_similar_summaries(current_summary, normalized_summary) or are_similar_tags(current_tags, list(summary.tags)):
            current_frame_indices.append(summary.index)
            current_tags = _merge_tags(current_tags, summary.tags)
            continue

        entries.append(
            TimelineEntry(
                start_seconds=current_start,
                end_seconds=summary.time_seconds,
                summary=current_display_summary,
                frame_indices=current_frame_indices,
                tags=current_tags,
            )
        )
        current_summary = normalized_summary
        current_start = summary.time_seconds
        current_frame_indices = [summary.index]
        current_display_summary = summary.summary.strip()
        current_tags = list(summary.tags)

    entries.append(
        TimelineEntry(
            start_seconds=current_start,
            end_seconds=video.duration_seconds,
            summary=current_display_summary,
            frame_indices=current_frame_indices,
            tags=current_tags,
        )
    )
    return entries


def _normalize_summary(summary: str) -> str:
    return " ".join(summary.strip().split())


def are_similar_summaries(first: str, second: str) -> bool:
    normalized_first = _normalize_summary(first)
    normalized_second = _normalize_summary(second)
    if normalized_first == normalized_second:
        return True

    first_tokens = _summary_tokens(normalized_first)
    second_tokens = _summary_tokens(normalized_second)
    if not first_tokens or not second_tokens:
        return False

    overlap = first_tokens & second_tokens
    union = first_tokens | second_tokens
    return len(overlap) / len(union) >= SUMMARY_SIMILARITY_THRESHOLD


def are_similar_tags(first: list[str] | tuple[str, ...], second: list[str] | tuple[str, ...]) -> bool:
    first_tags = set(first)
    second_tags = set(second)
    if not first_tags or not second_tags:
        return False

    overlap = first_tags & second_tags
    union = first_tags | second_tags
    return len(overlap) / len(union) >= TAG_SIMILARITY_THRESHOLD


def _merge_tags(current_tags: list[str], new_tags: tuple[str, ...]) -> list[str]:
    merged = list(current_tags)
    seen = set(merged)
    for tag in new_tags:
        if tag in seen:
            continue
        seen.add(tag)
        merged.append(tag)
    return merged


def _summary_tokens(summary: str) -> set[str]:
    normalized_summary = summary.casefold()
    tokens = set(re.findall(r"[a-z0-9_]+", normalized_summary))
    for sequence in re.findall(r"[一-龯ぁ-んァ-ンー]+", normalized_summary):
        tokens.update(_character_bigrams(sequence))
    return {token for token in tokens if token not in _SUMMARY_STOP_WORDS}


def _character_bigrams(text: str) -> set[str]:
    if len(text) < 2:
        return {text}
    return {text[index : index + 2] for index in range(len(text) - 1)}


_SUMMARY_STOP_WORDS = {
    "して",
    "いる",
    "ユーザー",
    "よう",
    "です",
    "につ",
    "つい",
    "いて",
}
