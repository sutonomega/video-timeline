from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


class TimelineSearchError(ValueError):
    pass


@dataclass(frozen=True)
class TimelineSearchResult:
    index: int
    start_seconds: float
    end_seconds: float
    summary: str


def search_timeline_document(document: dict, query: str) -> list[TimelineSearchResult]:
    normalized_query = query.casefold().strip()
    if not normalized_query:
        raise TimelineSearchError("queryを指定してください。")

    timeline = document.get("timeline")
    if not isinstance(timeline, list):
        raise TimelineSearchError("timeline JSONにtimelineがありません。")

    events_by_timeline_index = _build_events_by_timeline_index(document)
    results = []
    for index, entry in enumerate(timeline):
        if not isinstance(entry, dict):
            raise TimelineSearchError(f"timeline entryが不正です: {index}")
        if _matches_timeline_entry(entry, events_by_timeline_index.get(index, []), normalized_query):
            results.append(_build_search_result(index, entry))

    return results


def search_timeline_file(timeline_json_path: str | Path, query: str) -> list[TimelineSearchResult]:
    document = load_timeline_search_document(timeline_json_path)
    return search_timeline_document(document, query)


def load_timeline_search_document(timeline_json_path: str | Path) -> dict:
    path = Path(timeline_json_path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TimelineSearchError(f"timeline JSONが存在しません: {path}") from exc
    except json.JSONDecodeError as exc:
        raise TimelineSearchError(f"timeline JSONを読み取れません: {path}") from exc


def format_search_result(result: TimelineSearchResult) -> str:
    return (
        f"{result.index}  "
        f"{format_timestamp(result.start_seconds)}-{format_timestamp(result.end_seconds)}  "
        f"{result.summary}"
    )


def format_timestamp(seconds: float) -> str:
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"
    return f"{minutes:02d}:{remaining_seconds:02d}"


def _build_events_by_timeline_index(document: dict) -> dict[int, list[dict]]:
    events = document.get("events", [])
    if events is None:
        return {}
    if not isinstance(events, list):
        raise TimelineSearchError("timeline JSONのeventsが不正です。")

    events_by_timeline_index: dict[int, list[dict]] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        timeline_index = event.get("timeline_index")
        if isinstance(timeline_index, int):
            events_by_timeline_index.setdefault(timeline_index, []).append(event)
    return events_by_timeline_index


def _matches_timeline_entry(entry: dict, events: list[dict], normalized_query: str) -> bool:
    haystacks = list(_timeline_search_values(entry))
    for event in events:
        haystacks.extend(_event_search_values(event))
    return any(normalized_query in value.casefold() for value in haystacks)


def _timeline_search_values(entry: dict) -> list[str]:
    values = []
    summary = entry.get("summary")
    if isinstance(summary, str):
        values.append(summary)
    tags = entry.get("tags", [])
    if isinstance(tags, list):
        values.extend(tag for tag in tags if isinstance(tag, str))
    return values


def _event_search_values(event: dict) -> list[str]:
    values = []
    kind = event.get("kind")
    if isinstance(kind, str):
        values.append(kind)
    summary = event.get("summary")
    if isinstance(summary, str):
        values.append(summary)
    tags = event.get("tags", [])
    if isinstance(tags, list):
        values.extend(tag for tag in tags if isinstance(tag, str))
    return values


def _build_search_result(index: int, entry: dict) -> TimelineSearchResult:
    start_seconds = entry.get("start_seconds")
    end_seconds = entry.get("end_seconds")
    summary = entry.get("summary")
    if not isinstance(start_seconds, (int, float)) or not isinstance(end_seconds, (int, float)):
        raise TimelineSearchError(f"timeline entryにstart_seconds/end_secondsがありません: {index}")
    if not isinstance(summary, str):
        raise TimelineSearchError(f"timeline entryにsummaryがありません: {index}")

    return TimelineSearchResult(
        index=index,
        start_seconds=float(start_seconds),
        end_seconds=float(end_seconds),
        summary=summary,
    )
