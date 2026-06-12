"""
Archive service — dual-track isolation (hidden from timeline but not physically deleted).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.photo import Photo


async def archive_photo(photo_id: int, db: AsyncSession) -> Photo | None:
    """Move a photo to the archive (hide from main timeline)."""
    result = await db.execute(
        select(Photo).where(Photo.id == photo_id, Photo.is_deleted.is_(False))
    )
    photo = result.scalar_one_or_none()
    if not photo:
        return None
    photo.is_archived = True
    photo.archived_at = datetime.utcnow()
    await db.commit()
    await db.refresh(photo)
    return photo


async def unarchive_photo(photo_id: int, db: AsyncSession) -> Photo | None:
    """Restore a photo from the archive back to the main timeline."""
    result = await db.execute(
        select(Photo).where(Photo.id == photo_id, Photo.is_deleted.is_(False))
    )
    photo = result.scalar_one_or_none()
    if not photo:
        return None
    photo.is_archived = False
    photo.archived_at = None
    await db.commit()
    await db.refresh(photo)
    return photo


async def list_archived_photos(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 60,
) -> tuple[list[Photo], int]:
    """Return paginated list of archived (non-deleted) photos."""
    from sqlalchemy import func

    base_stmt = select(Photo).where(
        Photo.is_archived.is_(True),
        Photo.is_deleted.is_(False),
    )
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total: int = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        base_stmt
        .order_by(Photo.archived_at.desc().nullslast(), Photo.taken_at.desc().nullslast())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all()), total
