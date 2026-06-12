"""
Photo service — full CRUD + paginated list with filtering.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.photo import Photo


async def get_photo_by_id(photo_id: int, db: AsyncSession) -> Photo | None:
    result = await db.execute(select(Photo).where(Photo.id == photo_id))
    return result.scalar_one_or_none()


async def list_photos(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
    sort_by: str = "taken_at",
    order: str = "desc",
    only_duplicates: bool = False,
    min_sharpness: float | None = None,
) -> tuple[list[Photo], int]:
    """
    Return (photos, total_count) for the given page/filter.

    Supports:
      - Pagination (page / page_size)
      - Sort by any Photo column (default: taken_at desc)
      - Filter: duplicates only, minimum sharpness score
    """
    allowed_sort = {
        "taken_at", "file_size", "width", "height",
        "sharpness_score", "exposure_score", "created_at",
    }
    if sort_by not in allowed_sort:
        sort_by = "taken_at"

    col = getattr(Photo, sort_by, Photo.taken_at)
    order_expr = col.desc() if order == "desc" else col.asc()

    stmt = select(Photo).where(Photo.is_deleted.is_(False), Photo.is_archived.is_(False))

    if only_duplicates:
        stmt = stmt.where(Photo.duplicate_group_id.is_not(None))

    if min_sharpness is not None:
        stmt = stmt.where(Photo.sharpness_score >= min_sharpness)

    # Total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = (await db.execute(count_stmt)).scalar_one()

    # Paginated results
    stmt = stmt.order_by(order_expr).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    photos = list(result.scalars().all())

    return photos, total


async def soft_delete_photo(photo_id: int, db: AsyncSession) -> Photo | None:
    from app.services.album_service import soft_delete_photo as _soft_delete
    photo = await get_photo_by_id(photo_id, db)
    if photo is None:
        return None
    return await _soft_delete(db, photo)


async def get_dashboard_stats(db: AsyncSession) -> dict:
    """
    Aggregate statistics for the dashboard.
    Returns counts, sizes, quality breakdown, and last scan info.
    """
    from sqlalchemy import case, cast, Float
    from app.models.scan_task import ScanTask, ScanStatus

    base = select(Photo).where(Photo.is_deleted.is_(False))

    # Total count + total size
    agg = await db.execute(
        select(
            func.count(Photo.id).label("total"),
            func.coalesce(func.sum(Photo.file_size), 0).label("total_size"),
        ).where(Photo.is_deleted.is_(False))
    )
    row = agg.one()
    total: int = row.total
    total_size: int = row.total_size

    # Duplicate count + reclaimable space
    dup_agg = await db.execute(
        select(
            func.count(Photo.id).label("dup_count"),
            func.coalesce(func.sum(Photo.file_size), 0).label("dup_size"),
        ).where(
            Photo.is_deleted.is_(False),
            Photo.duplicate_group_id.is_not(None),
        )
    )
    dup_row = dup_agg.one()

    # Quality breakdown
    BLUR_THRESHOLD = 100.0
    quality_agg = await db.execute(
        select(
            func.count(
                case((Photo.sharpness_score < BLUR_THRESHOLD, 1))
            ).label("blurry"),
            func.count(
                case((Photo.exposure_score < 0.05, 1))
            ).label("underexposed"),
            func.count(
                case((Photo.exposure_score > 0.95, 1))
            ).label("overexposed"),
        ).where(Photo.is_deleted.is_(False))
    )
    q_row = quality_agg.one()

    # AI-tagged count
    tagged_agg = await db.execute(
        select(func.count(Photo.id)).where(
            Photo.is_deleted.is_(False),
            Photo.ai_caption.is_not(None),
        )
    )
    ai_tagged_count: int = tagged_agg.scalar_one()

    # Person count (from face clustering)
    from app.models.person import Person
    persons_agg = await db.execute(
        select(func.count(Person.id)).where(Person.is_hidden.is_(False))
    )
    total_persons: int = persons_agg.scalar_one()

    # Last completed scan
    last_scan = await db.execute(
        select(ScanTask)
        .where(ScanTask.status == ScanStatus.COMPLETED)
        .order_by(ScanTask.finished_at.desc())
        .limit(1)
    )
    last_scan_row = last_scan.scalar_one_or_none()

    return {
        "total_photos": total,
        "total_size_bytes": total_size,
        "duplicate_count": dup_row.dup_count,
        "reclaimable_bytes": dup_row.dup_size,
        "blurry_count": q_row.blurry,
        "underexposed_count": q_row.underexposed,
        "overexposed_count": q_row.overexposed,
        "ai_tagged_count": ai_tagged_count,
        "total_persons": total_persons,
        "last_scan_at": last_scan_row.finished_at.isoformat() if last_scan_row else None,
        "last_scan_path": last_scan_row.scan_path if last_scan_row else None,
    }
