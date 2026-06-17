from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path


DEFAULT_TRANSCRIPT_SOURCE = "external_asr"


class TranscriptLoaderError(ValueError):
    pass


@dataclass(frozen=True)
class TranscriptSegment:
    start_seconds: float
    end_seconds: float
    text: str
    source: str = DEFAULT_TRANSCRIPT_SOURCE
    speaker: str | None = None

    def to_dict(self) -> dict[str, float | str]:
        payload: dict[str, float | str] = {
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "text": self.text,
            "source": self.source,
        }
        if self.speaker is not None:
            payload["speaker"] = self.speaker
        return payload


def load_transcript_segments(path: str | Path | None) -> list[TranscriptSegment]:
    if path is None:
        return []

    transcript_path = Path(path)
    if not transcript_path.is_file():
        raise TranscriptLoaderError(f"transcript JSONが存在しません: {transcript_path}")

    try:
        payload = json.loads(transcript_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TranscriptLoaderError(f"transcript JSONを読み取れません: {transcript_path}") from exc

    segments_payload = _extract_segments_payload(payload)
    segments = [_parse_segment(segment, index) for index, segment in enumerate(segments_payload)]
    return sorted(segments, key=lambda segment: (segment.start_seconds, segment.end_seconds, segment.text))


def _extract_segments_payload(payload: object) -> list[object]:
    if isinstance(payload, list):
        return payload

    if not isinstance(payload, Mapping):
        raise TranscriptLoaderError("transcript JSONは配列またはオブジェクトにしてください")

    for key in ("transcripts", "segments"):
        value = payload.get(key)
        if value is not None:
            if not isinstance(value, list):
                raise TranscriptLoaderError(f"transcript JSONの{key}は配列にしてください")
            return value

    raise TranscriptLoaderError("transcript JSONにはtranscriptsまたはsegmentsが必要です")


def _parse_segment(payload: object, index: int) -> TranscriptSegment:
    if not isinstance(payload, Mapping):
        raise TranscriptLoaderError(f"transcript segmentはオブジェクトにしてください: index={index}")

    start_seconds = _read_seconds(payload, "start_seconds", fallback_key="start", index=index)
    end_seconds = _read_seconds(payload, "end_seconds", fallback_key="end", index=index)
    if end_seconds <= start_seconds:
        raise TranscriptLoaderError(f"transcript segmentのend_secondsはstart_secondsより後にしてください: index={index}")

    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        raise TranscriptLoaderError(f"transcript segmentには空ではないtextが必要です: index={index}")

    source = payload.get("source", DEFAULT_TRANSCRIPT_SOURCE)
    if not isinstance(source, str) or not source.strip():
        source = DEFAULT_TRANSCRIPT_SOURCE

    speaker = payload.get("speaker")
    normalized_speaker = speaker.strip() if isinstance(speaker, str) and speaker.strip() else None

    return TranscriptSegment(
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        text=text.strip(),
        source=source.strip(),
        speaker=normalized_speaker,
    )


def _read_seconds(payload: Mapping[str, object], key: str, *, fallback_key: str, index: int) -> float:
    value = payload.get(key, payload.get(fallback_key))
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TranscriptLoaderError(f"transcript segmentには数値の{key}が必要です: index={index}")
    if value < 0:
        raise TranscriptLoaderError(f"transcript segmentの{key}は0以上にしてください: index={index}")
    return float(value)
