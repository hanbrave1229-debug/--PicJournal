"""
Video streaming API — HTTP Range-aware byte-range streaming.

Design: serve the original file directly (no transcoding — NAS CPU would be
saturated). Modern browsers play H.264 MP4/MOV natively. Partial content
(206) is returned for Range requests so the player can seek without
re-downloading.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.photo_service import get_photo_by_id

router = APIRouter()

_MIME: dict[str, str] = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska",
    ".m4v": "video/x-m4v",
    ".hevc": "video/mp4",
    ".webm": "video/webm",
}

_CHUNK = 1 << 20  # 1 MB read chunks


@router.get("/{photo_id}/stream", summary="Stream video file with Range support")
async def stream_video(
    photo_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    photo = await get_photo_by_id(photo_id, db)
    if photo is None:
        raise HTTPException(status_code=404, detail="Video not found")
    if getattr(photo, "media_type", "photo") != "video":
        raise HTTPException(status_code=400, detail="Not a video")

    path = Path(photo.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    file_size = path.stat().st_size
    mime = _MIME.get(path.suffix.lower(), "video/mp4")

    range_header = request.headers.get("range")
    if range_header:
        # Parse "bytes=start-end"
        try:
            unit, rng = range_header.split("=", 1)
            start_s, end_s = rng.split("-", 1)
            start = int(start_s) if start_s else 0
            end = int(end_s) if end_s else file_size - 1
        except Exception:
            raise HTTPException(status_code=416, detail="Invalid Range header")

        end = min(end, file_size - 1)
        if start > end or start < 0:
            raise HTTPException(status_code=416, detail="Range not satisfiable")

        content_length = end - start + 1

        def _iter_range():
            with open(path, "rb") as f:
                f.seek(start)
                remaining = content_length
                while remaining > 0:
                    chunk = f.read(min(_CHUNK, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Cache-Control": "no-cache",
        }
        return StreamingResponse(_iter_range(), status_code=206, media_type=mime, headers=headers)

    # Full file response
    def _iter_full():
        with open(path, "rb") as f:
            while True:
                chunk = f.read(_CHUNK)
                if not chunk:
                    break
                yield chunk

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(file_size),
        "Cache-Control": "no-cache",
    }
    return StreamingResponse(_iter_full(), status_code=200, media_type=mime, headers=headers)
