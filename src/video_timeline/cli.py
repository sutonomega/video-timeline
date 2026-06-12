from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys
import time

from .event_detector import detect_events
from .frame_extractor import DEFAULT_INTERVAL_SECONDS, ExtractedFrame, extract_frames
from .frame_summarizer import (
    AnalysisMetadata,
    DEFAULT_VL_MODEL,
    build_frame_summary_document,
    save_frame_summary_json,
    summarize_frames_with_ollama,
)
from .timeline_generator import build_timeline
from .video_loader import load_video_metadata


def print_progress(message: str) -> None:
    print(message, flush=True)


class FrameSummarizationProgress:
    def __init__(self) -> None:
        self.started_at = time.monotonic()

    def __call__(self, current: int, total: int, frame: ExtractedFrame) -> None:
        remaining = self._format_remaining(current, total)
        print_progress(
            f"frame summarization started: {current}/{total} "
            f"({frame.time_seconds:g}s, remaining: {remaining})"
        )

    def _format_remaining(self, current: int, total: int) -> str:
        completed = current - 1
        remaining = total - completed
        if completed <= 0:
            return "calculating"

        elapsed_seconds = time.monotonic() - self.started_at
        average_seconds = elapsed_seconds / completed
        remaining_seconds = round(average_seconds * remaining)
        return format_duration(remaining_seconds)


def format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"

    minutes, remaining_seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {remaining_seconds}s"

    hours, remaining_minutes = divmod(minutes, 60)
    return f"{hours}h {remaining_minutes}m {remaining_seconds}s"


def build_run_frames_dir(video_path: str | Path, frames_dir: str | Path) -> Path:
    resolved_video_path = Path(video_path).resolve(strict=False)
    path_hash = hashlib.sha256(str(resolved_video_path).encode("utf-8")).hexdigest()[:12]
    return Path(frames_dir) / f"{resolved_video_path.stem}_{path_hash}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate frame summary JSON from a video.")
    parser.add_argument("input", help="入力動画ファイルのパス")
    parser.add_argument("--output", required=True, help="出力JSONファイルのパス")
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=DEFAULT_INTERVAL_SECONDS,
        help="フレーム抽出間隔。既定値は10秒",
    )
    parser.add_argument("--frames-dir", default="frames", help="抽出フレームの保存先")
    return parser


def run(args: argparse.Namespace) -> Path:
    print_progress("動画メタデータ取得中")
    video = load_video_metadata(args.input)
    print_progress("フレーム抽出中")
    frames = extract_frames(
        video,
        frames_dir=build_run_frames_dir(video.path, args.frames_dir),
        interval_seconds=args.interval_seconds,
    )
    print_progress("フレーム要約中")
    frame_summaries = summarize_frames_with_ollama(
        frames,
        model=DEFAULT_VL_MODEL,
        progress=FrameSummarizationProgress(),
    )
    print_progress("タイムライン生成中")
    timeline = build_timeline(frame_summaries, video)
    print_progress("イベント生成中")
    events = detect_events(timeline)
    print_progress("JSON保存中")
    document = build_frame_summary_document(
        video=video,
        analysis=AnalysisMetadata(interval_seconds=args.interval_seconds),
        frame_summaries=frame_summaries,
        timeline=timeline,
        events=events,
    )
    output_path = Path(args.output)
    save_frame_summary_json(document, output_path)
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output_path = run(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
