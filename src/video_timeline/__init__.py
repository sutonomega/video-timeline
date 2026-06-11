"""Video Timeline package."""

from .frame_extractor import ExtractedFrame, FrameExtractorError, extract_frames
from .video_loader import VideoLoaderError, VideoMetadata, load_video_metadata

__all__ = [
    "ExtractedFrame",
    "FrameExtractorError",
    "VideoLoaderError",
    "VideoMetadata",
    "extract_frames",
    "load_video_metadata",
]
