"""
Photos API — paginated list and single photo detail.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.photo import Photo
from app.schemas.photo import PhotoListResponse, PhotoResponse
from app.services.photo_service import get_photo_by_id, list_photos, soft_delete_photo

router = APIRouter()


@router.get("", response_model=PhotoListResponse, summary="List photos with pagination")
async def list_photos_endpoint(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sort_by: str = Query("taken_at"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    only_duplicates: bool = Query(False),
    min_sharpness: float | None = Query(None),
    date_from: str | None = Query(None, description="Filter photos taken on or after this date (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Filter photos taken on or before this date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
) -> PhotoListResponse:
    photos, total = await list_photos(
        db,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        order=order,
        only_duplicates=only_duplicates,
        min_sharpness=min_sharpness,
        date_from=date_from,
        date_to=date_to,
    )
    return PhotoListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[PhotoResponse.from_orm(p) for p in photos],
    )


class PickerPhotoItem(BaseModel):
    id: int
    thumbnail_256: str | None
    taken_at: datetime | None
    province: str | None = None
    city: str | None = None


class PickerResponse(BaseModel):
    year: int
    month: int
    total: int
    photos: List[PickerPhotoItem]


@router.get("/picker", response_model=PickerResponse, summary="按年月筛选照片，供日记封面选择器使用")
async def get_photos_for_picker(
    year: int = Query(..., ge=2000, le=2100, description="年份"),
    month: int = Query(..., ge=1, le=12, description="月份 (1-12)"),
    db: AsyncSession = Depends(get_db),
) -> PickerResponse:
    """
    返回指定年月内所有未删除、未归档的照片（仅缩略图 + 时间 + 地理），
    用于日记弹窗跨月挑选封面快照。按 taken_at 倒序排列。
    """
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)

    stmt = (
        select(Photo)
        .where(
            and_(
                Photo.is_deleted.is_(False),
                Photo.is_archived.is_(False),
                Photo.taken_at >= start,
                Photo.taken_at < end,
            )
        )
        .order_by(Photo.taken_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()

    items = [
        PickerPhotoItem(
            id=p.id,
            thumbnail_256=p.thumbnail_256,
            taken_at=p.taken_at,
            province=p.province,
            city=p.city,
        )
        for p in rows
    ]
    return PickerResponse(year=year, month=month, total=len(items), photos=items)


@router.get("/{photo_id}", response_model=PhotoResponse, summary="Get single photo detail")
async def get_photo(
    photo_id: int,
    db: AsyncSession = Depends(get_db),
) -> PhotoResponse:
    photo = await get_photo_by_id(photo_id, db)
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    return PhotoResponse.from_orm(photo)


@router.get("/{photo_id}/file", response_class=FileResponse, summary="Serve original file")
async def get_photo_file(
    photo_id: int,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Serve the original photo file directly from disk (for full-res viewing)."""
    photo = await get_photo_by_id(photo_id, db)
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    p = Path(photo.file_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    ext = p.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".gif": "image/gif",
        ".webp": "image/webp", ".heic": "image/heic",
        ".heif": "image/heif", ".bmp": "image/bmp",
    }
    return FileResponse(
        str(p),
        media_type=media_types.get(ext, "application/octet-stream"),
        headers={"Cache-Control": "max-age=3600"},
    )


@router.delete("/{photo_id}", summary="Soft-delete a photo")
async def delete_photo(
    photo_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    photo = await soft_delete_photo(photo_id, db)
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    return {"id": photo_id, "deleted": True}
