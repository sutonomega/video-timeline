from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import base64
import json
from pathlib import Path
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
DEFAULT_SUMMARY_PROMPT = "この画像でユーザーが何をしているかを日本語で1文で要約してください。"


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

    def to_dict(self) -> dict[str, float | int | str]:
        return {
            "index": self.index,
            "time_seconds": self.time_seconds,
            "image": self.image,
            "summary": self.summary,
        }


FrameSummaryFunction = Callable[[ExtractedFrame], str]
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
        summary = summarize_image(frame).strip()
        if not summary:
            raise FrameSummarizerError(f"空の要約が返されました: {frame.image}")
        summaries.append(
            FrameSummary(
                index=frame.index,
                time_seconds=frame.time_seconds,
                image=frame.image,
                summary=summary,
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
) -> str:
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

    summary = response_payload.get("response")
    if not isinstance(summary, str) or not summary.strip():
        raise FrameSummarizerError("Ollama APIから要約文を取得できません。")
    return summary.strip()


def _utc_now_isoformat() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
