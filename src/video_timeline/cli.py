from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .event_detector import detect_events
from .frame_extractor import DEFAULT_INTERVAL_SECONDS, extract_frames
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
    frames = extract_frames(video, frames_dir=args.frames_dir, interval_seconds=args.interval_seconds)
    print_progress("フレーム要約中")
    frame_summaries = summarize_frames_with_ollama(
        frames,
        model=DEFAULT_VL_MODEL,
        progress=lambda current, total, frame: print_progress(f"frame summarization: {current}/{total} ({frame.time_seconds:g}s)"),
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
