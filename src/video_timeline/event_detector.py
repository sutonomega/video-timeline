from __future__ import annotations

from dataclasses import dataclass

from .timeline_generator import TimelineEntry


DEFAULT_EVENT_KIND = "activity"
IMPORTANCE_DURATION_FULL_SCORE_SECONDS = 60.0
MIN_IMPORTANCE_SCORE = 0.1
EVENT_KIND_IMPORTANCE_BONUS = {
    "review": 0.15,
    "terminal": 0.15,
    "coding": 0.1,
    "chat": 0.1,
    "cooking": 0.05,
}
EVENT_KIND_RULES = (
    ("review", ("review", "code_review", "pull_request", "github", "prレビュー", "pr確認", "レビュー")),
    ("terminal", ("terminal", "shell", "git", "command", "コマンド", "ターミナル")),
    ("coding", ("coding", "code_editor", "vscode", "python", "implementation", "実装", "コード")),
    ("chat", ("chatgpt", "chat", "planning", "相談", "検討", "要件")),
    ("cooking", ("cooking", "oatmeal", "rice_cooker", "eating", "料理", "調理", "食事", "お粥")),
    ("browser", ("browser", "youtube", "discord", "document", "game", "ブラウザ")),
)


@dataclass(frozen=True)
class EventCandidate:
    kind: str
    start_seconds: float
    end_seconds: float
    summary: str
    timeline_index: int
    importance_score: float

    def to_dict(self) -> dict[str, float | int | str]:
        return {
            "kind": self.kind,
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "summary": self.summary,
            "timeline_index": self.timeline_index,
            "importance_score": self.importance_score,
        }


def detect_events(timeline: list[TimelineEntry]) -> list[EventCandidate]:
    events: list[EventCandidate] = []
    indexed_timeline = sorted(enumerate(timeline), key=lambda item: (item[1].start_seconds, item[1].end_seconds, item[0]))
    for timeline_index, entry in indexed_timeline:
        kind = classify_event_kind(entry)
        events.append(
            EventCandidate(
                kind=kind,
                start_seconds=entry.start_seconds,
                end_seconds=entry.end_seconds,
                summary=entry.summary,
                timeline_index=timeline_index,
                importance_score=calculate_importance_score(entry, kind),
            )
        )
    return events


def classify_event_kind(entry: TimelineEntry) -> str:
    haystack = " ".join([entry.summary, *entry.tags]).casefold()
    for kind, keywords in EVENT_KIND_RULES:
        if any(keyword.casefold() in haystack for keyword in keywords):
            return kind
    return DEFAULT_EVENT_KIND


def calculate_importance_score(entry: TimelineEntry, kind: str | None = None) -> float:
    duration_seconds = max(0.0, entry.end_seconds - entry.start_seconds)
    score = duration_seconds / IMPORTANCE_DURATION_FULL_SCORE_SECONDS
    score += EVENT_KIND_IMPORTANCE_BONUS.get(kind or classify_event_kind(entry), 0.0)
    return round(min(1.0, max(MIN_IMPORTANCE_SCORE, score)), 2)
