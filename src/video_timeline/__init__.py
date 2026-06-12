"""Video Timeline package."""

from .frame_extractor import ExtractedFrame, FrameExtractorError, extract_frames
from .frame_summarizer import (
    AnalysisMetadata,
    FrameSummarizerError,
    FrameSummary,
    FrameSummaryContent,
    build_frame_summary_document,
    normalize_tags,
    parse_frame_summary_response,
    save_frame_summary_json,
    summarize_frames,
    summarize_frames_with_ollama,
    summarize_image_with_ollama,
)
from .video_loader import VideoLoaderError, VideoMetadata, load_video_metadata
from .video_clipper import VideoClipperError, clip_timeline_entry

__all__ = [
    "AnalysisMetadata",
    "ExtractedFrame",
    "FrameExtractorError",
    "FrameSummarizerError",
    "FrameSummary",
    "FrameSummaryContent",
    "VideoClipperError",
    "VideoLoaderError",
    "VideoMetadata",
    "build_frame_summary_document",
    "clip_timeline_entry",
    "extract_frames",
    "load_video_metadata",
    "normalize_tags",
    "parse_frame_summary_response",
    "save_frame_summary_json",
    "summarize_frames",
    "summarize_frames_with_ollama",
    "summarize_image_with_ollama",
]
