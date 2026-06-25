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

    # NOTE: we run ffmpeg via exec (no shell), so the scale filter must NOT be
    # shell-quoted. The comma inside min() must be backslash-escaped, otherwise
    # ffmpeg treats it as a filtergraph separator and fails with
    # "-22 Invalid argument". (Shell quotes like 'min(1920,iw)' would be passed
    # literally here and also break parsing.)
    _scale = r"scale=min(1920\,iw):-2"  # cap width at 1920px, keep AR (even h)

    def _build_cmd(seek: float | None) -> list[str]:
        cmd = ["ffmpeg", "-y"]
        if seek and seek > 0:
            cmd += ["-ss", str(seek)]   # seek before input (fast)
        cmd += [
            "-i", video_path,
            "-frames:v", "1",
            "-q:v", "2",
            "-vf", _scale,
            output_jpeg,
        ]
        return cmd

    async def _run(cmd: list[str]) -> tuple[bool, str]:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return False, "timeout"
        ok = proc.returncode == 0 and Path(output_jpeg).exists()
        return ok, stderr.decode(errors="replace")[-300:]

    async with _get_sem():
        try:
            # First try seeking; if it fails (e.g. seek past EOF on very short
            # clips / live photos), retry grabbing the first frame.
            ok, err = await _run(_build_cmd(seek_seconds))
            if ok:
                return True
            ok2, err2 = await _run(_build_cmd(None))
            if ok2:
                return True
            logger.warning(
                "FFmpeg frame extract failed for %s: %s | %s", video_path, err, err2
            )
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
