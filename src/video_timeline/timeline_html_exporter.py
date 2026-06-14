from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from .timeline_searcher import format_timestamp


class TimelineHtmlExportError(ValueError):
    pass


def export_timeline_html_file(timeline_json_path: str | Path, output_path: str | Path) -> Path:
    document = load_timeline_html_document(timeline_json_path)
    html_document = build_timeline_html_document(document)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_document, encoding="utf-8")
    return path


def load_timeline_html_document(timeline_json_path: str | Path) -> dict:
    path = Path(timeline_json_path)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TimelineHtmlExportError(f"timeline JSONが存在しません: {path}") from exc
    except json.JSONDecodeError as exc:
        raise TimelineHtmlExportError(f"timeline JSONを読み取れません: {path}") from exc

    if not isinstance(document, dict):
        raise TimelineHtmlExportError("timeline JSONのルートが不正です。")
    return document


def build_timeline_html_document(document: dict) -> str:
    timeline = document.get("timeline")
    if not isinstance(timeline, list):
        raise TimelineHtmlExportError("timeline JSONにtimelineがありません。")

    video = _optional_mapping(document.get("video"))
    analysis = _optional_mapping(document.get("analysis"))
    events = document.get("events", [])
    if events is None:
        events = []
    if not isinstance(events, list):
        raise TimelineHtmlExportError("timeline JSONのeventsが不正です。")

    title = _html_text(_string_value(video.get("path"), "Video Timeline"))
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="ja">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{title}</title>",
            "</head>",
            "<body>",
            "<h1>Video Timeline</h1>",
            "<h2>Video</h2>",
            _build_key_value_table(video),
            "<h2>Analysis</h2>",
            _build_key_value_table(analysis),
            "<h2>Timeline</h2>",
            _build_timeline_table(timeline),
            "<h2>Events</h2>",
            _build_events_table(events),
            "</body>",
            "</html>",
            "",
        ]
    )


def _build_key_value_table(mapping: dict[str, Any]) -> str:
    if not mapping:
        return "<p>No data</p>"

    rows = []
    for key in sorted(mapping):
        rows.append(
            "<tr>"
            f"<th>{_html_text(str(key))}</th>"
            f"<td>{_html_text(_display_value(mapping[key]))}</td>"
            "</tr>"
        )
    return "<table><tbody>" + "".join(rows) + "</tbody></table>"


def _build_timeline_table(timeline: list) -> str:
    rows = []
    for index, entry in enumerate(timeline):
        if not isinstance(entry, dict):
            raise TimelineHtmlExportError(f"timeline entryが不正です: {index}")
        rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{_html_text(_format_range(entry))}</td>"
            f"<td>{_html_text(_string_value(entry.get('summary')))}</td>"
            f"<td>{_html_text(_format_tags(entry.get('tags')))}</td>"
            "</tr>"
        )
    return (
        "<table>"
        "<thead><tr><th>index</th><th>time</th><th>summary</th><th>tags</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


def _build_events_table(events: list) -> str:
    rows = []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise TimelineHtmlExportError(f"event entryが不正です: {index}")
        rows.append(
            "<tr>"
            f"<td>{_html_text(_string_value(event.get('kind')))}</td>"
            f"<td>{_html_text(_format_range(event))}</td>"
            f"<td>{_html_text(_string_value(event.get('summary')))}</td>"
            f"<td>{_html_text(_display_value(event.get('timeline_index')))}</td>"
            f"<td>{_html_text(_display_value(event.get('importance_score')))}</td>"
            f"<td>{_html_text(_format_tags(event.get('tags')))}</td>"
            "</tr>"
        )

    return (
        "<table>"
        "<thead>"
        "<tr>"
        "<th>kind</th><th>time</th><th>summary</th>"
        "<th>timeline_index</th><th>importance_score</th><th>tags</th>"
        "</tr>"
        "</thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


def _format_range(entry: dict) -> str:
    start_seconds = entry.get("start_seconds")
    end_seconds = entry.get("end_seconds")
    if not isinstance(start_seconds, (int, float)) or not isinstance(end_seconds, (int, float)):
        return ""
    return f"{format_timestamp(float(start_seconds))}-{format_timestamp(float(end_seconds))}"


def _format_tags(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    return ", ".join(str(tag) for tag in value if isinstance(tag, str))


def _optional_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _string_value(value: Any, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _display_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _html_text(value: str) -> str:
    return html.escape(value, quote=True)
