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
    StorageMetadata,
    build_frame_summary_document,
    save_frame_summary_json,
    summarize_frames_with_ollama,
)
from .scene_detector import safe_detect_scene_boundaries
from .app_config import (
    load_app_config,
    resolve_batch_paths,
    resolve_clip_paths,
    resolve_export_html_paths,
    resolve_timeline_json_path,
    resolve_video_run_paths,
)
from .timeline_generator import build_timeline
from .timeline_html_exporter import export_timeline_html_file
from .timeline_searcher import format_search_result, format_timestamp, search_timeline_file
from .transcript_loader import load_transcript_segments
from .video_clipper import clip_timeline_entries_by_tag, clip_timeline_entry, clip_timeline_entry_range
from .video_loader import load_video_metadata


DEFAULT_FRAMES_DIR = "frames"


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


class SceneDetectionProgress:
    def __init__(self, duration_seconds: float) -> None:
        self.duration_seconds = max(duration_seconds, 0.0)
        self.last_reported_second: int | None = None

    def __call__(self, processed_seconds: float) -> None:
        current_second = int(processed_seconds)
        if self.last_reported_second == current_second:
            return
        self.last_reported_second = current_second

        if self.duration_seconds <= 0:
            print_progress(f"scene detection progress: {format_timestamp(current_second)}")
            return

        bounded_second = min(current_second, int(self.duration_seconds))
        percent = min(100, round((bounded_second / self.duration_seconds) * 100))
        print_progress(
            "scene detection progress: "
            f"{format_timestamp(bounded_second)}/{format_timestamp(self.duration_seconds)} "
            f"({percent}%)"
        )


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
    parser.add_argument("--batch", action="store_true", help="設定された入力ディレクトリ配下のmp4を一括解析する")
    parser.add_argument("--input-dir", help="一括解析する入力ディレクトリ")
    parser.add_argument("--output-dir", help="一括解析結果の保存先ベースディレクトリ")
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=DEFAULT_INTERVAL_SECONDS,
        help="フレーム抽出間隔。既定値は10秒",
    )
    parser.add_argument("--frames-dir", default=DEFAULT_FRAMES_DIR, help="抽出フレームの保存先")
    parser.add_argument("--vl-model", default=DEFAULT_VL_MODEL, help=f"フレーム要約に使うOllamaモデル。既定値は{DEFAULT_VL_MODEL}")
    parser.add_argument("--transcript-json", help="外部ASR結果のJSONをtranscriptsとして保存する")
    return parser


def build_clip_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clip a timeline segment from a video.")
    parser.add_argument("timeline_json", help="timeline JSONファイルのパス")
    parser.add_argument("--index", type=int, help="切り出すtimeline index")
    parser.add_argument("--start-index", type=int, help="連続切り出しの開始timeline index")
    parser.add_argument("--end-index", type=int, help="連続切り出しの終了timeline index")
    parser.add_argument("--tag", help="指定タグを含むtimeline区間を切り出す")
    parser.add_argument("--output", help="切り出しMP4の保存先、または複数切り出しの出力ディレクトリ")
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
    parser.add_argument(
        "--crf",
        type=int,
        help="--accurate時のx264画質。既定値は18",
    )
    parser.add_argument(
        "--preset",
        help="--accurate時のx264エンコード速度。既定値はveryfast",
    )
    return parser


def build_search_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search timeline segments.")
    parser.add_argument("timeline_json", help="timeline JSONファイルのパス")
    parser.add_argument("query", help="検索キーワード")
    return parser


def build_export_html_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export timeline JSON to static HTML.")
    parser.add_argument("timeline_json", help="timeline JSONファイルのパス")
    parser.add_argument("--output", help="出力HTMLファイルのパス")
    return parser


def run_clip(args: argparse.Namespace) -> Path | list[Path]:
    has_single_index = args.index is not None
    has_range = args.start_index is not None or args.end_index is not None
    has_tag = args.tag is not None
    selected_modes = sum([has_single_index, has_range, has_tag])
    if selected_modes > 1:
        raise ValueError("--index、--start-index/--end-index、--tagは同時に指定できません")
    if selected_modes == 0:
        raise ValueError("--index、--start-index/--end-index、--tagのいずれかを指定してください")
    if has_range and (args.start_index is None or args.end_index is None):
        raise ValueError("--start-indexと--end-indexは両方指定してください")

    timeline_json, output_path = resolve_clip_paths(
        args.timeline_json,
        args.output,
        output_is_directory=not has_single_index,
        config=load_app_config(),
    )

    if has_single_index:
        return clip_timeline_entry(
            timeline_json,
            index=args.index,
            output_path=output_path,
            padding_seconds=args.padding_seconds,
            accurate=args.accurate,
            crf=args.crf,
            preset=args.preset,
        )

    if has_tag:
        return clip_timeline_entries_by_tag(
            timeline_json,
            tag=args.tag,
            output_dir=output_path,
            padding_seconds=args.padding_seconds,
            accurate=args.accurate,
            crf=args.crf,
            preset=args.preset,
        )

    return clip_timeline_entry_range(
        timeline_json,
        start_index=args.start_index,
        end_index=args.end_index,
        output_dir=output_path,
        padding_seconds=args.padding_seconds,
        accurate=args.accurate,
        crf=args.crf,
        preset=args.preset,
    )


def run_search(args: argparse.Namespace) -> list[str]:
    timeline_json = resolve_timeline_json_path(args.timeline_json, load_app_config())
    return [format_search_result(result) for result in search_timeline_file(timeline_json, args.query)]


def run_export_html(args: argparse.Namespace) -> Path:
    timeline_json, output_path = resolve_export_html_paths(
        args.timeline_json,
        args.output,
        load_app_config(),
    )
    return export_timeline_html_file(timeline_json, output_path)


def run_video(
    input_path: str | Path,
    output_path: str | Path,
    frames_dir: str | Path,
    interval_seconds: float,
    *,
    isolate_frames: bool = True,
    vl_model: str = DEFAULT_VL_MODEL,
    transcript_json: str | Path | None = None,
) -> Path:
    print_progress("動画メタデータ取得中")
    video = load_video_metadata(input_path)
    print_progress("シーン境界検出中")
    scene_boundaries = safe_detect_scene_boundaries(
        video.path,
        progress=SceneDetectionProgress(video.duration_seconds),
    )
    if transcript_json is not None:
        print_progress("音声文字起こし読み込み中")
    transcripts = load_transcript_segments(transcript_json)
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
        model=vl_model,
        progress=FrameSummarizationProgress(),
    )
    print_progress("タイムライン生成中")
    timeline = build_timeline(frame_summaries, video)
    print_progress("イベント生成中")
    events = detect_events(timeline)
    print_progress("JSON保存中")
    document = build_frame_summary_document(
        video=video,
        analysis=AnalysisMetadata(interval_seconds=interval_seconds, vl_model=vl_model),
        storage=StorageMetadata(
            video_path=video.path,
            frames_dir=str(actual_frames_dir),
            timeline_path=str(output_path),
        ),
        scene_boundaries=scene_boundaries,
        transcripts=transcripts,
        frame_summaries=frame_summaries,
        timeline=timeline,
        events=events,
    )
    path = Path(output_path)
    save_frame_summary_json(document, path)
    return path


def run_batch(args: argparse.Namespace, config=None) -> tuple[int, int]:
    if args.transcript_json is not None:
        raise ValueError("--transcript-jsonはbatch CLIでは指定できません")

    input_dir, output_dir = resolve_batch_paths(args.input_dir, args.output_dir, config)
    if input_dir is None:
        raise ValueError("--batchを使う場合はvideo_timeline.tomlまたは--input-dirが必要です")
    if output_dir is None:
        raise ValueError("--batchまたは--input-dirを使う場合は--output-dirが必要です")
    if args.input is not None or args.output is not None:
        raise ValueError("--batchまたは--input-dirを使う場合はinputと--outputは指定できません")

    success_count = 0
    failure_count = 0
    processed_count = 0
    for video_path in discover_mp4_files(input_dir):
        processed_count += 1
        video_dir = build_batch_video_dir(video_path, output_dir)
        print_progress(f"batch video started: {video_path}")
        try:
            output_path = run_video(
                video_path,
                video_dir / "timeline.json",
                video_dir / "frames",
                args.interval_seconds,
                isolate_frames=False,
                vl_model=args.vl_model,
                transcript_json=None,
            )
        except Exception as exc:
            failure_count += 1
            print(f"batch video failed: {video_path}: {exc}", file=sys.stderr)
            continue

        success_count += 1
        print_progress(f"wrote {output_path}")

    if processed_count == 0:
        raise ValueError(f"mp4が見つかりません: {input_dir}")

    return success_count, failure_count


def run(args: argparse.Namespace) -> Path | tuple[int, int]:
    config = load_app_config()
    if args.batch or args.input_dir is not None:
        return run_batch(args, config)
    if args.input is None:
        raise ValueError("inputまたは--input-dirが必要です")

    input_path, output_path, frames_dir = resolve_video_run_paths(
        args.input,
        args.output,
        args.frames_dir,
        config,
    )
    if output_path is None:
        raise ValueError("--outputが必要です")

    return run_video(
        input_path,
        output_path,
        frames_dir,
        args.interval_seconds,
        vl_model=args.vl_model,
        transcript_json=args.transcript_json,
    )


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "export-html":
        parser = build_export_html_parser()
        args = parser.parse_args(argv[1:])
        try:
            output_path = run_export_html(args)
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print(f"wrote {output_path}")
        return 0

    if argv and argv[0] == "search":
        parser = build_search_parser()
        args = parser.parse_args(argv[1:])
        try:
            lines = run_search(args)
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        if not lines:
            print("no matches")
        else:
            for line in lines:
                print(line)
        return 0

    if argv and argv[0] == "clip":
        parser = build_clip_parser()
        args = parser.parse_args(argv[1:])
        try:
            output_path = run_clip(args)
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        if isinstance(output_path, list):
            if not output_path:
                print("no matches")
            else:
                for path in output_path:
                    print(f"wrote {path}")
        else:
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
