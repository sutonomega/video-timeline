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
DEFAULT_SUMMARY_PROMPT = (
    "この画像でユーザーが何をしているかを日本語で1文で要約し、検索用タグも付けてください。"
    '必ずJSONだけで返してください。形式: {"summary":"日本語の要約","tags":["chatgpt","coding"]}'
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
class FrameSummary:
    index: int
    time_seconds: float
    image: str
    summary: str
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, float | int | str | list[str]]:
        return {
            "index": self.index,
            "time_seconds": self.time_seconds,
            "image": self.image,
            "summary": self.summary,
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class FrameSummaryContent:
    summary: str
    tags: tuple[str, ...] = ()


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
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return FrameSummaryContent(summary=text)

    if not isinstance(payload, dict):
        return FrameSummaryContent(summary=text)

    summary = payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise FrameSummarizerError("Ollama APIから要約文を取得できません。")

    raw_tags = payload.get("tags", [])
    if not isinstance(raw_tags, list):
        raw_tags = []
    return FrameSummaryContent(summary=summary.strip(), tags=normalize_tags(raw_tags))


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
        return FrameSummaryContent(summary=value.summary.strip(), tags=normalize_tags(list(value.tags)))
    return FrameSummaryContent(summary=value.strip())


def _utc_now_isoformat() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
