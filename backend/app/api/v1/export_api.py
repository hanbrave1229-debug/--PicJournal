"""
Export API — stream photo selections and albums as ZIP archives.

Endpoints
---------
POST /export/photos          body: {photo_ids, filename}  → ZIP of originals
GET  /export/album/{id}      → ZIP of album photos
POST /export/albums          body: {album_ids, filename}  → ZIP, one sub-folder per album
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.album import Album, AlbumPhoto
from app.models.photo import Photo

router = APIRouter()

# ── Helpers ────────────────────────────────────────────────────────────────────

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif", ".bmp", ".tiff", ".tif"}


def _safe_name(name: str) -> str:
    """Strip filesystem-unsafe chars from ZIP filename."""
    return "".join(c if c.isalnum() or c in " ._-" else "_" for c in name)


async def _fetch_photos(db: AsyncSession, photo_ids: list[int]) -> list[Photo]:
    result = await db.execute(
        select(Photo).where(Photo.id.in_(photo_ids), Photo.is_deleted.is_(False))
    )
    return list(result.scalars().all())


def _build_zip_stream(photos: list[Photo], root_prefix: str = "") -> io.BytesIO:
    """
    Build an in-memory ZIP from a list of Photo rows.
    `root_prefix` adds a folder layer (e.g., album name).
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as zf:
        name_count: dict[str, int] = {}
        for photo in photos:
            src = Path(photo.file_path)
            if not src.exists():
                continue
            base = src.name
            # De-duplicate filenames within the archive
            key = base.lower()
            if key in name_count:
                name_count[key] += 1
                stem, suffix = src.stem, src.suffix
                base = f"{stem}_{name_count[key]}{suffix}"
            else:
                name_count[key] = 0

            arc_name = f"{root_prefix}/{base}" if root_prefix else base
            zf.write(str(src), arc_name)
    buf.seek(0)
    return buf


# ── Endpoints ──────────────────────────────────────────────────────────────────

class ExportPhotosRequest(BaseModel):
    photo_ids: list[int]
    filename: str = "photos_export"


class ExportAlbumsRequest(BaseModel):
    album_ids: list[int]
    filename: str = "albums_export"


@router.post("/photos", summary="导出选定照片为 ZIP")
async def export_photos(
    body: ExportPhotosRequest,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Download the original files for the given photo IDs as a single ZIP archive.
    Returns 404 if none of the requested photos exist on disk.
    """
    if not body.photo_ids:
        raise HTTPException(status_code=422, detail="photo_ids must not be empty")

    photos = await _fetch_photos(db, body.photo_ids)
    photos = [p for p in photos if Path(p.file_path).exists()]
    if not photos:
        raise HTTPException(status_code=404, detail="No valid photo files found for the given IDs")

    buf = _build_zip_stream(photos)
    safe = _safe_name(body.filename) or "photos_export"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe}.zip"'},
    )


@router.get("/album/{album_id}", summary="导出整个相册为 ZIP")
async def export_album(
    album_id: int,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Download all photos in an album as a ZIP."""
    result = await db.execute(select(Album).where(Album.id == album_id))
    album = result.scalar_one_or_none()
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    ap_result = await db.execute(
        select(AlbumPhoto).where(AlbumPhoto.album_id == album_id)
    )
    ap_rows = ap_result.scalars().all()
    if not ap_rows:
        raise HTTPException(status_code=404, detail="Album has no photos")

    photo_ids = [r.photo_id for r in ap_rows]
    photos = await _fetch_photos(db, photo_ids)
    photos = [p for p in photos if Path(p.file_path).exists()]
    if not photos:
        raise HTTPException(status_code=404, detail="No valid photo files found in album")

    buf = _build_zip_stream(photos, root_prefix=_safe_name(album.title))
    safe = _safe_name(album.title) or f"album_{album_id}"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe}.zip"'},
    )


@router.post("/albums", summary="批量导出多个相册为一个 ZIP（按相册分子文件夹）")
async def export_albums(
    body: ExportAlbumsRequest,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Download multiple albums in one ZIP.
    Each album's photos are placed in a sub-folder named after the album.
    """
    if not body.album_ids:
        raise HTTPException(status_code=422, detail="album_ids must not be empty")

    buf = io.BytesIO()
    total_written = 0

    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as zf:
        for album_id in body.album_ids:
            result = await db.execute(select(Album).where(Album.id == album_id))
            album = result.scalar_one_or_none()
            if not album:
                continue

            ap_result = await db.execute(
                select(AlbumPhoto).where(AlbumPhoto.album_id == album_id)
            )
            photo_ids = [r.photo_id for r in ap_result.scalars().all()]
            if not photo_ids:
                continue

            photos = await _fetch_photos(db, photo_ids)
            folder = _safe_name(album.title) or f"album_{album_id}"
            name_count: dict[str, int] = {}

            for photo in photos:
                src = Path(photo.file_path)
                if not src.exists():
                    continue
                base = src.name
                key = base.lower()
                if key in name_count:
                    name_count[key] += 1
                    base = f"{src.stem}_{name_count[key]}{src.suffix}"
                else:
                    name_count[key] = 0
                zf.write(str(src), f"{folder}/{base}")
                total_written += 1

    if total_written == 0:
        raise HTTPException(status_code=404, detail="No valid photo files found across the given albums")

    buf.seek(0)
    safe = _safe_name(body.filename) or "albums_export"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe}.zip"'},
    )
