from __future__ import annotations

from dataclasses import dataclass

from .timeline_generator import TimelineEntry


DEFAULT_EVENT_KIND = "activity"


@dataclass(frozen=True)
class EventCandidate:
    kind: str
    start_seconds: float
    end_seconds: float
    summary: str
    timeline_index: int

    def to_dict(self) -> dict[str, float | int | str]:
        return {
            "kind": self.kind,
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "summary": self.summary,
            "timeline_index": self.timeline_index,
        }


def detect_events(timeline: list[TimelineEntry]) -> list[EventCandidate]:
    events: list[EventCandidate] = []
    indexed_timeline = sorted(enumerate(timeline), key=lambda item: (item[1].start_seconds, item[1].end_seconds, item[0]))
    for timeline_index, entry in indexed_timeline:
        events.append(
            EventCandidate(
                kind=DEFAULT_EVENT_KIND,
                start_seconds=entry.start_seconds,
                end_seconds=entry.end_seconds,
                summary=entry.summary,
                timeline_index=timeline_index,
            )
        )
    return events
