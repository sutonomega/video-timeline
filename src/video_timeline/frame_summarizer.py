from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import base64
import json
from pathlib import Path
import re
from typing import TYPE_CHECKING, Callable
from urllib import request, error

from .frame_extractor import ExtractedFrame
from .video_loader import VideoMetadata

if TYPE_CHECKING:
    from .event_detector import EventCandidate
    from .timeline_generator import TimelineEntry


DEFAULT_VL_PROVIDER = "ollama"
DEFAULT_VL_MODEL = "qwen2.5vl:7b"
DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_PRIMARY_TAG = "other"
SCREEN_PRIMARY_TAGS = (
    "chatgpt",
    "github",
    "vscode",
    "terminal",
    "browser",
    "youtube",
    "discord",
    "game",
    "document",
)
LIFE_PRIMARY_TAGS = (
    "cooking",
    "oatmeal",
    "rice_cooker",
    "eating",
    "shopping",
    "walking",
    "exercise",
    "cleaning",
    "travel",
    "study",
)
DEFAULT_SUMMARY_PROMPT = (
    "この画像でユーザーが何をしているかを日本語で1文で要約してください。"
    "画面の主対象をprimary_tagに1つだけ入れ、補助的な作業や文脈をsecondary_tagsに入れてください。"
    "PCやスマホの画面が主対象ならprimary_tagは次から選んでください: "
    f"{', '.join(SCREEN_PRIMARY_TAGS)}。"
    "料理、食事、家事、外出、移動などの生活動画が主対象ならprimary_tagは次から選んでください: "
    f"{', '.join(LIFE_PRIMARY_TAGS)}。"
    "適切な候補がない場合は、短い自由タグを使ってください。"
    "secondary_tagsは必ず配列キーsecondary_tagsとして返してください。secondary_tags[]は使わないでください。"
    '必ずJSONだけで返してください。形式: {"summary":"日本語の要約","primary_tag":"chatgpt","secondary_tags":["planning"]}'
)


class FrameSummarizerError(ValueError):
    pass


@dataclass(frozen=True)
class AnalysisMetadata:
    interval_seconds: float
    vl_provider: str = DEFAULT_VL_PROVIDER
    vl_model: str = DEFAULT_VL_MODEL

    def to_dict(self) -> dict[str, float | str]:
        return {
            "interval_seconds": self.interval_seconds,
            "vl_provider": self.vl_provider,
            "vl_model": self.vl_model,
        }


@dataclass(frozen=True)
class StorageMetadata:
    mode: str
    video_path: str
    frames_dir: str
    timeline_path: str

    def to_dict(self) -> dict[str, str]:
        if self.mode not in ("local", "server"):
            raise FrameSummarizerError(f"不正なstorage modeです: {self.mode}")
        return {
            "mode": self.mode,
            "video_path": self.video_path,
            "frames_dir": self.frames_dir,
            "timeline_path": self.timeline_path,
        }


@dataclass(frozen=True)
class FrameSummary:
    index: int
    time_seconds: float
    image: str
    summary: str
    tags: tuple[str, ...] = ()
    primary_tag: str = DEFAULT_PRIMARY_TAG
    secondary_tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, float | int | str | list[str]]:
        primary_tag, secondary_tags, tags = _resolve_tag_fields(
            self.primary_tag,
            self.secondary_tags,
            self.tags,
        )
        return {
            "index": self.index,
            "time_seconds": self.time_seconds,
            "image": self.image,
            "summary": self.summary,
            "primary_tag": primary_tag,
            "secondary_tags": list(secondary_tags),
            "tags": list(tags),
        }


@dataclass(frozen=True)
class FrameSummaryContent:
    summary: str
    tags: tuple[str, ...] = ()
    primary_tag: str = DEFAULT_PRIMARY_TAG
    secondary_tags: tuple[str, ...] = ()


FrameSummaryFunction = Callable[[ExtractedFrame], FrameSummaryContent | str]
FrameSummaryProgress = Callable[[int, int, ExtractedFrame], None]


def summarize_frames(
    frames: list[ExtractedFrame],
    summarize_image: FrameSummaryFunction,
    progress: FrameSummaryProgress | None = None,
) -> list[FrameSummary]:
    summaries: list[FrameSummary] = []
    sorted_frames = sorted(frames, key=lambda item: item.time_seconds)
    total_frames = len(sorted_frames)
    for position, frame in enumerate(sorted_frames, start=1):
        if progress is not None:
            progress(position, total_frames, frame)
        content = _coerce_frame_summary_content(summarize_image(frame))
        if not content.summary:
            raise FrameSummarizerError(f"空の要約が返されました: {frame.image}")
        summaries.append(
            FrameSummary(
                index=frame.index,
                time_seconds=frame.time_seconds,
                image=frame.image,
                summary=content.summary,
                tags=content.tags,
                primary_tag=content.primary_tag,
                secondary_tags=content.secondary_tags,
            )
        )
    return summaries


def summarize_frames_with_ollama(
    frames: list[ExtractedFrame],
    model: str = DEFAULT_VL_MODEL,
    prompt: str = DEFAULT_SUMMARY_PROMPT,
    api_url: str = DEFAULT_OLLAMA_URL,
    progress: FrameSummaryProgress | None = None,
) -> list[FrameSummary]:
    return summarize_frames(
        frames,
        lambda frame: summarize_image_with_ollama(
            frame.image,
            model=model,
            prompt=prompt,
            api_url=api_url,
        ),
        progress=progress,
    )


def build_frame_summary_document(
    video: VideoMetadata,
    analysis: AnalysisMetadata,
    frame_summaries: list[FrameSummary],
    storage: StorageMetadata | None = None,
    timeline: list[TimelineEntry] | None = None,
    events: list[EventCandidate] | None = None,
    generated_at: str | None = None,
) -> dict:
    document = {
        "version": 1,
        "generated_at": generated_at or _utc_now_isoformat(),
        "video": video.to_dict(),
        "analysis": analysis.to_dict(),
        "frame_summaries": [summary.to_dict() for summary in sorted(frame_summaries, key=lambda item: item.time_seconds)],
    }
    if storage is not None:
        document["storage"] = storage.to_dict()
    if timeline is not None:
        document["timeline"] = [entry.to_dict() for entry in timeline]
    if events is not None:
        document["events"] = [event.to_dict() for event in events]
    return document


def save_frame_summary_json(document: dict, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def summarize_image_with_ollama(
    image_path: str | Path,
    model: str = DEFAULT_VL_MODEL,
    prompt: str = DEFAULT_SUMMARY_PROMPT,
    api_url: str = DEFAULT_OLLAMA_URL,
) -> FrameSummaryContent:
    try:
        image_bytes = Path(image_path).read_bytes()
    except FileNotFoundError as exc:
        raise FrameSummarizerError(f"画像ファイルが存在しません: {image_path}") from exc

    payload = {
        "model": model,
        "prompt": prompt,
        "images": [base64.b64encode(image_bytes).decode("ascii")],
        "stream": False,
    }
    request_body = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        api_url,
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=120) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except error.URLError as exc:
        raise FrameSummarizerError(f"Ollama APIへ接続できません: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise FrameSummarizerError("Ollama APIの応答JSONを読み取れません。") from exc

    response_text = response_payload.get("response")
    if not isinstance(response_text, str) or not response_text.strip():
        raise FrameSummarizerError("Ollama APIから要約文を取得できません。")
    return parse_frame_summary_response(response_text)


def parse_frame_summary_response(response_text: str) -> FrameSummaryContent:
    text = response_text.strip()
    payload = _load_json_object_from_text(text)
    if payload is None:
        return FrameSummaryContent(summary=text)

    summary = payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise FrameSummarizerError("Ollama APIから要約文を取得できません。")

    nested_payload = _load_json_object_from_text(summary.strip()) if summary.strip().startswith("{") else None
    if nested_payload is not None and nested_payload.get("summary"):
        payload = nested_payload
        summary = nested_payload["summary"]

    primary_tag = payload.get("primary_tag")
    raw_secondary_tags = payload.get("secondary_tags")
    if not isinstance(raw_secondary_tags, list):
        raw_secondary_tags = payload.get("secondary_tags[]")
    raw_tags = payload.get("tags")

    if isinstance(raw_secondary_tags, list) or isinstance(primary_tag, str):
        secondary_tags = normalize_tags(raw_secondary_tags if isinstance(raw_secondary_tags, list) else [])
        resolved_primary_tag, resolved_secondary_tags, tags = _resolve_tag_fields(primary_tag, secondary_tags, ())
    else:
        legacy_tags = normalize_tags(raw_tags if isinstance(raw_tags, list) else [])
        resolved_primary_tag, resolved_secondary_tags, tags = _resolve_tag_fields(None, (), legacy_tags)

    return FrameSummaryContent(
        summary=summary.strip(),
        tags=tags,
        primary_tag=resolved_primary_tag,
        secondary_tags=resolved_secondary_tags,
    )


def _load_json_object_from_text(text: str) -> dict | None:
    candidates = [text]
    repaired_text = _repair_common_json_text(text)
    if repaired_text != text:
        candidates.append(repaired_text)
    extracted = _extract_json_object_text(text)
    if extracted and extracted not in candidates:
        candidates.append(extracted)
    repaired_extracted = _extract_json_object_text(repaired_text)
    if repaired_extracted and repaired_extracted not in candidates:
        candidates.append(repaired_extracted)

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload

    recovered = _recover_partial_frame_summary(text)
    if recovered is not None:
        return recovered
    return None


def _extract_json_object_text(text: str) -> str | None:
    start_index = text.find("{")
    if start_index == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for index in range(start_index, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start_index : index + 1]

    return None


def _repair_common_json_text(text: str) -> str:
    return text.replace('"secondary_tags[]"', '"secondary_tags"')


def _recover_partial_frame_summary(text: str) -> dict | None:
    summary = _extract_json_string_field(text, "summary")
    primary_tag = _extract_json_string_field(text, "primary_tag")
    if summary is None or primary_tag is None:
        return None
    return {
        "summary": summary,
        "primary_tag": primary_tag,
        "secondary_tags": [],
    }


def _extract_json_string_field(text: str, field_name: str) -> str | None:
    pattern = rf'"{re.escape(field_name)}"\s*:\s*"((?:\\.|[^"\\])*)"'
    match = re.search(pattern, text)
    if match is None:
        return None
    raw_value = match.group(1)
    try:
        return json.loads(f'"{raw_value}"')
    except json.JSONDecodeError:
        return None


def normalize_tags(raw_tags: list[object]) -> tuple[str, ...]:
    tags: list[str] = []
    seen: set[str] = set()
    for raw_tag in raw_tags:
        if not isinstance(raw_tag, str):
            continue
        tag = re.sub(r"[^a-z0-9_一-龯ぁ-んァ-ンー]+", "_", raw_tag.strip().casefold().replace("-", "_"))
        tag = re.sub(r"_+", "_", tag).strip("_")
        if not tag or tag in seen:
            continue
        seen.add(tag)
        tags.append(tag)
    return tuple(tags)


def _coerce_frame_summary_content(value: FrameSummaryContent | str) -> FrameSummaryContent:
    if isinstance(value, FrameSummaryContent):
        primary_tag, secondary_tags, tags = _resolve_tag_fields(value.primary_tag, value.secondary_tags, value.tags)
        return FrameSummaryContent(
            summary=value.summary.strip(),
            tags=tags,
            primary_tag=primary_tag,
            secondary_tags=secondary_tags,
        )
    return FrameSummaryContent(summary=value.strip())


def _resolve_tag_fields(
    primary_tag: object,
    secondary_tags: tuple[str, ...] | list[object],
    tags: tuple[str, ...] | list[object],
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    normalized_tags = normalize_tags(list(tags))
    normalized_secondary_tags = normalize_tags(list(secondary_tags))
    normalized_primary_tags = normalize_tags([primary_tag] if isinstance(primary_tag, str) else [])

    resolved_primary_tag = normalized_primary_tags[0] if normalized_primary_tags else ""
    if resolved_primary_tag == DEFAULT_PRIMARY_TAG and normalized_tags:
        resolved_primary_tag = ""
    if not resolved_primary_tag and normalized_tags:
        resolved_primary_tag = normalized_tags[0]
    if not resolved_primary_tag:
        resolved_primary_tag = DEFAULT_PRIMARY_TAG

    if not normalized_secondary_tags and normalized_tags:
        normalized_secondary_tags = tuple(tag for tag in normalized_tags if tag != resolved_primary_tag)
    else:
        normalized_secondary_tags = tuple(tag for tag in normalized_secondary_tags if tag != resolved_primary_tag)

    resolved_tags = normalize_tags([resolved_primary_tag, *normalized_secondary_tags])
    return resolved_primary_tag, normalized_secondary_tags, resolved_tags


def _utc_now_isoformat() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
