"""
Thumbnails API — serve generated thumbnail images.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.thumbnail_gen import generate_thumbnails
from app.db.database import get_db
from app.services.photo_service import get_photo_by_id

router = APIRouter()


@router.get("/{photo_id}", response_class=FileResponse, summary="Get thumbnail image")
async def get_thumbnail(
    photo_id: int,
    size: int = Query(256, description="Thumbnail size in px: 256 or 1080"),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """
    Return the cached thumbnail for a photo.
    If not yet generated, triggers on-demand generation before responding.
    """
    from app.config import get_settings

    settings = get_settings()

    if size not in settings.thumbnail_sizes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid size. Supported: {list(settings.thumbnail_sizes)}",
        )

    photo = await get_photo_by_id(photo_id, db)
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Check cached path stored in DB
    cached_path: str | None = getattr(photo, f"thumbnail_{size}", None)
    if cached_path and Path(cached_path).exists():
        return FileResponse(cached_path, media_type="image/jpeg")

    # On-demand generation
    results = await generate_thumbnails(photo.file_path, photo.id)
    thumb_path = results.get(size)

    if not thumb_path or not Path(thumb_path).exists():
        raise HTTPException(status_code=500, detail="Thumbnail generation failed")

    # Persist path back to DB
    setattr(photo, f"thumbnail_{size}", thumb_path)
    db.add(photo)
    await db.commit()

    return FileResponse(thumb_path, media_type="image/jpeg")
