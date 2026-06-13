from __future__ import annotations

import argparse
from collections.abc import Iterator
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
from .video_clipper import clip_timeline_entry
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


def build_batch_video_dir(video_path: str | Path, output_dir: str | Path) -> Path:
    return build_run_frames_dir(video_path, output_dir)


def discover_mp4_files(input_dir: str | Path) -> Iterator[Path]:
    directory = Path(input_dir)
    if not directory.is_dir():
        raise ValueError(f"入力ディレクトリが存在しません: {directory}")

    for path in directory.rglob("*"):
        if path.is_file() and path.suffix.lower() == ".mp4":
            yield path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate frame summary JSON from a video.")
    parser.add_argument("input", nargs="?", help="入力動画ファイルのパス")
    parser.add_argument("--output", help="出力JSONファイルのパス")
    parser.add_argument("--input-dir", help="一括解析する入力ディレクトリ")
    parser.add_argument("--output-dir", help="一括解析結果の保存先ベースディレクトリ")
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=DEFAULT_INTERVAL_SECONDS,
        help="フレーム抽出間隔。既定値は10秒",
    )
    parser.add_argument("--frames-dir", default="frames", help="抽出フレームの保存先")
    return parser


def build_clip_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clip a timeline segment from a video.")
    parser.add_argument("timeline_json", help="timeline JSONファイルのパス")
    parser.add_argument("--index", type=int, required=True, help="切り出すtimeline index")
    parser.add_argument("--output", required=True, help="切り出しMP4の保存先")
    parser.add_argument(
        "--padding-seconds",
        type=float,
        default=0.0,
        help="切り出し範囲の前後に足す余白秒数。既定値は0秒",
    )
    parser.add_argument(
        "--accurate",
        action="store_true",
        help="再エンコードして開始位置の正確さを優先する",
    )
    return parser


def run_video(
    input_path: str | Path,
    output_path: str | Path,
    frames_dir: str | Path,
    interval_seconds: float,
    *,
    isolate_frames: bool = True,
) -> Path:
    print_progress("動画メタデータ取得中")
    video = load_video_metadata(input_path)
    print_progress("フレーム抽出中")
    actual_frames_dir = build_run_frames_dir(video.path, frames_dir) if isolate_frames else Path(frames_dir)
    frames = extract_frames(
        video,
        frames_dir=actual_frames_dir,
        interval_seconds=interval_seconds,
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
        analysis=AnalysisMetadata(interval_seconds=interval_seconds),
        frame_summaries=frame_summaries,
        timeline=timeline,
        events=events,
    )
    path = Path(output_path)
    save_frame_summary_json(document, path)
    return path


def run_batch(args: argparse.Namespace) -> tuple[int, int]:
    if args.output_dir is None:
        raise ValueError("--input-dirを使う場合は--output-dirが必要です")
    if args.input is not None or args.output is not None:
        raise ValueError("--input-dirを使う場合はinputと--outputは指定できません")

    success_count = 0
    failure_count = 0
    processed_count = 0
    for video_path in discover_mp4_files(args.input_dir):
        processed_count += 1
        video_dir = build_batch_video_dir(video_path, args.output_dir)
        print_progress(f"batch video started: {video_path}")
        try:
            output_path = run_video(
                video_path,
                video_dir / "timeline.json",
                video_dir / "frames",
                args.interval_seconds,
                isolate_frames=False,
            )
        except Exception as exc:
            failure_count += 1
            print(f"batch video failed: {video_path}: {exc}", file=sys.stderr)
            continue

        success_count += 1
        print_progress(f"wrote {output_path}")

    if processed_count == 0:
        raise ValueError(f"mp4が見つかりません: {args.input_dir}")

    return success_count, failure_count


def run(args: argparse.Namespace) -> Path | tuple[int, int]:
    if args.input_dir is not None:
        return run_batch(args)
    if args.input is None:
        raise ValueError("inputまたは--input-dirが必要です")
    if args.output is None:
        raise ValueError("--outputが必要です")

    return run_video(args.input, args.output, args.frames_dir, args.interval_seconds)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "clip":
        parser = build_clip_parser()
        args = parser.parse_args(argv[1:])
        try:
            output_path = clip_timeline_entry(
                args.timeline_json,
                index=args.index,
                output_path=args.output,
                padding_seconds=args.padding_seconds,
                accurate=args.accurate,
            )
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"wrote {output_path}")
        return 0

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if isinstance(result, tuple):
        success_count, failure_count = result
        print(f"batch complete: success={success_count} failure={failure_count}")
    else:
        print(f"wrote {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
