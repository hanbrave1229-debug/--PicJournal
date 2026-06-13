"""
Video processor — FFmpeg-based thumbnail extraction and streaming helpers.

Design notes:
- Uses asyncio.create_subprocess_exec (non-blocking, no shell injection surface).
- Global Semaphore limits concurrent FFmpeg processes to settings.ffmpeg_max_concurrent
  so a single 4K transcode doesn't saturate the NAS CPU and kill other requests.
- Thumbnail extraction: jump to 00:00:01, extract one JPEG frame, feed to Pillow
  pipeline so the rest of the app treats it identically to a photo thumbnail.
- Streaming: HTTP Range-aware byte-range streaming of the original file.
  On-the-fly transcode is NOT done (too CPU-intensive for NAS); instead the
  original file is served directly. Most modern browsers can play H.264 MP4/MOV.
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Global semaphore — prevents more than N simultaneous FFmpeg processes.
_ffmpeg_sem: asyncio.Semaphore | None = None


def _get_sem() -> asyncio.Semaphore:
    global _ffmpeg_sem
    if _ffmpeg_sem is None:
        _ffmpeg_sem = asyncio.Semaphore(settings.ffmpeg_max_concurrent)
    return _ffmpeg_sem


def ffmpeg_available() -> bool:
    """Return True if ffmpeg binary is on PATH."""
    return shutil.which("ffmpeg") is not None


async def extract_video_frame(
    video_path: str,
    output_jpeg: str,
    seek_seconds: float = 1.0,
) -> bool:
    """
    Extract a single JPEG frame from *video_path* at *seek_seconds* and save
    to *output_jpeg*. Returns True on success.

    The output JPEG is a full-resolution frame; caller should pass it through
    thumbnail_gen.generate_thumbnails() to get the standard 256/1080px sizes.
    """
    if not ffmpeg_available():
        logger.warning("ffmpeg not found — video thumbnail extraction skipped")
        return False

    Path(output_jpeg).parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",                          # overwrite without prompting
        "-ss", str(seek_seconds),      # seek before input (fast)
        "-i", video_path,
        "-frames:v", "1",              # extract exactly one frame
        "-q:v", "2",                   # JPEG quality (2 = high, 31 = low)
        "-vf", "scale='min(1920,iw)':-2",  # cap width at 1920px, keep AR
        output_jpeg,
    ]

    async with _get_sem():
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode != 0:
                logger.warning(
                    "FFmpeg frame extract failed for %s: %s",
                    video_path,
                    stderr.decode(errors="replace")[-300:],
                )
                return False
            return Path(output_jpeg).exists()
        except asyncio.TimeoutError:
            logger.warning("FFmpeg timed out for %s", video_path)
            try:
                proc.kill()
            except Exception:
                pass
            return False
        except Exception as exc:
            logger.warning("FFmpeg error for %s: %s", video_path, exc)
            return False


async def get_video_duration(video_path: str) -> float | None:
    """
    Use ffprobe to get video duration in seconds.
    Returns None if ffprobe unavailable or file is unreadable.
    """
    if not shutil.which("ffprobe"):
        return None

    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        raw = stdout.decode().strip()
        return float(raw) if raw else None
    except Exception:
        return None


def format_duration(seconds: float | None) -> str:
    """Format duration as 'M:SS' or 'H:MM:SS'."""
    if seconds is None:
        return ""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"
