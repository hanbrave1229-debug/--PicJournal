"""
Archive API — dual-track photo isolation endpoints.

POST /archive/{photo_id}         → archive (hide from main timeline)
POST /archive/{photo_id}/restore → unarchive (restore to main timeline)
GET  /archive                    → list archived photos (paginated)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.photo import PhotoListResponse, PhotoResponse
from app.services import archive_service

router = APIRouter()


@router.post("/{photo_id}", response_model=PhotoResponse)
async def archive_photo(
    photo_id: int,
    db: AsyncSession = Depends(get_db),
) -> PhotoResponse:
    """Archive a photo — removes it from the main timeline without physical deletion."""
    photo = await archive_service.archive_photo(photo_id, db)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    return PhotoResponse.from_orm(photo)


@router.post("/{photo_id}/restore", response_model=PhotoResponse)
async def unarchive_photo(
    photo_id: int,
    db: AsyncSession = Depends(get_db),
) -> PhotoResponse:
    """Restore an archived photo back to the main timeline."""
    photo = await archive_service.unarchive_photo(photo_id, db)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    return PhotoResponse.from_orm(photo)


@router.get("", response_model=PhotoListResponse)
async def list_archive(
    page: int = Query(1, ge=1),
    page_size: int = Query(60, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> PhotoListResponse:
    """List all archived photos (paginated)."""
    photos, total = await archive_service.list_archived_photos(db, page, page_size)
    return PhotoListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[PhotoResponse.from_orm(p) for p in photos],
    )
