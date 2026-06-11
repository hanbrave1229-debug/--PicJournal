"""
Trash (soft-delete) API — soft delete, restore, hard delete, empty.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.photo import Photo
from app.schemas.album import TrashListResponse, TrashPhotoResponse
from app.services import album_service

router = APIRouter()


@router.get("", response_model=TrashListResponse)
async def list_trash(
    page: int = Query(1, ge=1),
    page_size: int = Query(60, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    photos, total = await album_service.list_trash(db, page, page_size)
    return TrashListResponse(
        items=[TrashPhotoResponse.model_validate(p) for p in photos],
        total=total,
    )


@router.delete("", status_code=200)
async def empty_trash(db: AsyncSession = Depends(get_db)):
    """Permanently delete all photos in the trash."""
    count = await album_service.empty_trash(db)
    return {"deleted": count}


@router.post("/{photo_id}/restore", status_code=200)
async def restore_photo(photo_id: int, db: AsyncSession = Depends(get_db)):
    photo = await _get_deleted(db, photo_id)
    await album_service.restore_photo(db, photo)
    return {"restored": photo_id}


@router.delete("/{photo_id}", status_code=204)
async def hard_delete_photo(photo_id: int, db: AsyncSession = Depends(get_db)):
    photo = await _get_deleted(db, photo_id)
    await album_service.hard_delete_photo(db, photo)


# ── Soft-delete entry point (called from photos API) ──────────────────────────

@router.delete("/photos/{photo_id}", status_code=200, include_in_schema=False)
async def soft_delete_photo(photo_id: int, db: AsyncSession = Depends(get_db)):
    """Move photo to trash (soft delete)."""
    result = await db.execute(select(Photo).where(Photo.id == photo_id))
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    await album_service.soft_delete_photo(db, photo)
    return {"deleted": photo_id}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_deleted(db: AsyncSession, photo_id: int) -> Photo:
    result = await db.execute(
        select(Photo).where(Photo.id == photo_id, Photo.is_deleted == True)  # noqa: E712
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found in trash")
    return photo
