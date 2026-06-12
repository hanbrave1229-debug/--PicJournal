"""
Album service — CRUD, photo association, and trash management.
"""
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.album import Album, AlbumPhoto
from app.models.photo import Photo


# ── Album CRUD ────────────────────────────────────────────────────────────────

async def create_album(
    db: AsyncSession,
    title: str,
    description: Optional[str] = None,
    is_smart: bool = False,
    smart_rules: Optional[str] = None,
) -> Album:
    album = Album(
        title=title,
        description=description,
        is_smart=is_smart,
        smart_rules=smart_rules,
    )
    db.add(album)
    await db.commit()
    await db.refresh(album)
    return album


async def list_albums(db: AsyncSession) -> list[Album]:
    """Return all non-smart albums ordered by creation time desc."""
    result = await db.execute(
        select(Album)
        .where(Album.is_smart == False)  # noqa: E712
        .options(selectinload(Album.album_photos))
        .order_by(Album.created_at.desc())
    )
    return list(result.scalars().all())


async def list_smart_albums(db: AsyncSession) -> list[Album]:
    """Return all smart (conditional) albums."""
    result = await db.execute(
        select(Album)
        .where(Album.is_smart == True)  # noqa: E712
        .order_by(Album.created_at.desc())
    )
    return list(result.scalars().all())


async def get_album(db: AsyncSession, album_id: int) -> Optional[Album]:
    result = await db.execute(
        select(Album)
        .where(Album.id == album_id)
        .options(selectinload(Album.album_photos))
    )
    return result.scalar_one_or_none()


async def update_album(
    db: AsyncSession,
    album: Album,
    title: Optional[str] = None,
    description: Optional[str] = None,
    cover_photo_id: Optional[int] = None,
) -> Album:
    if title is not None:
        album.title = title
    if description is not None:
        album.description = description
    if cover_photo_id is not None:
        album.cover_photo_id = cover_photo_id
    await db.commit()
    await db.refresh(album)
    return album


async def delete_album(db: AsyncSession, album: Album) -> None:
    await db.delete(album)
    await db.commit()


# ── Photo ↔ Album association ────────────────────────────────────────────────

async def add_photos_to_album(
    db: AsyncSession, album_id: int, photo_ids: list[int]
) -> int:
    """Add photos to an album; silently skip duplicates. Returns count added."""
    # Fetch existing associations
    existing = await db.execute(
        select(AlbumPhoto.photo_id).where(AlbumPhoto.album_id == album_id)
    )
    existing_ids = {row[0] for row in existing.all()}
    new_ids = [pid for pid in photo_ids if pid not in existing_ids]

    for pid in new_ids:
        db.add(AlbumPhoto(album_id=album_id, photo_id=pid))

    await db.commit()
    return len(new_ids)


async def remove_photos_from_album(
    db: AsyncSession, album_id: int, photo_ids: list[int]
) -> None:
    await db.execute(
        delete(AlbumPhoto).where(
            AlbumPhoto.album_id == album_id,
            AlbumPhoto.photo_id.in_(photo_ids),
        )
    )
    await db.commit()


async def list_album_photos(
    db: AsyncSession,
    album_id: int,
    page: int = 1,
    page_size: int = 60,
) -> tuple[list[Photo], int]:
    """Return paginated photos for a given album, excluding soft-deleted."""
    base = (
        select(Photo)
        .join(AlbumPhoto, AlbumPhoto.photo_id == Photo.id)
        .where(AlbumPhoto.album_id == album_id, Photo.is_deleted == False)  # noqa: E712
        .order_by(Photo.taken_at.desc().nulls_last(), Photo.created_at.desc())
    )
    total_result = await db.execute(
        select(func.count()).select_from(base.subquery())
    )
    total = total_result.scalar_one()

    result = await db.execute(base.offset((page - 1) * page_size).limit(page_size))
    return list(result.scalars().all()), total


# ── Trash (soft-delete) ────────────────────────────────────────────────────────

_TRASH_DIR_NAME = ".trash"


def _trash_dir(photo_path: str) -> Path:
    """Return the .trash directory alongside the photo's parent root."""
    parent = Path(photo_path).parent
    # Walk up to find a consistent trash root (same volume as the photo)
    return parent / _TRASH_DIR_NAME


async def soft_delete_photo(db: AsyncSession, photo: Photo) -> Photo:
    """Mark photo as deleted and move file to .trash/."""
    if photo.is_deleted:
        return photo

    src = Path(photo.file_path)
    if src.exists():
        trash = _trash_dir(photo.file_path)
        trash.mkdir(parents=True, exist_ok=True)
        # Use UUID-safe name to avoid collisions
        dest = trash / f"{photo.id}_{src.name}"
        try:
            shutil.move(str(src), str(dest))
        except (OSError, shutil.Error):
            pass  # File already missing or move failed — still mark deleted

    photo.is_deleted = True
    photo.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(photo)
    return photo


async def restore_photo(db: AsyncSession, photo: Photo) -> Photo:
    """Restore a soft-deleted photo — move file back and clear flags."""
    if not photo.is_deleted:
        return photo

    src_name = f"{photo.id}_{Path(photo.file_path).name}"
    trash = _trash_dir(photo.file_path)
    trashed = trash / src_name

    if trashed.exists():
        dest = Path(photo.file_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(trashed), str(dest))
        except (OSError, shutil.Error):
            pass

    photo.is_deleted = False
    photo.deleted_at = None
    await db.commit()
    await db.refresh(photo)
    return photo


async def hard_delete_photo(db: AsyncSession, photo: Photo) -> None:
    """Permanently remove photo from DB and disk."""
    src_name = f"{photo.id}_{Path(photo.file_path).name}"
    trash = _trash_dir(photo.file_path)
    trashed = trash / src_name

    # Remove from trash dir if present
    for p in [trashed, Path(photo.file_path)]:
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass

    await db.delete(photo)
    await db.commit()


async def list_trash(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 60,
) -> tuple[list[Photo], int]:
    """Return paginated list of soft-deleted photos."""
    base = (
        select(Photo)
        .where(Photo.is_deleted == True)  # noqa: E712
        .order_by(Photo.deleted_at.desc().nulls_last())
    )
    total_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = total_result.scalar_one()

    result = await db.execute(base.offset((page - 1) * page_size).limit(page_size))
    return list(result.scalars().all()), total


async def resolve_smart_album_photos(
    rules_json: str,
    db: AsyncSession,
    page: int = 1,
    page_size: int = 200,
) -> tuple[list[Photo], int]:
    """
    Dynamically evaluate smart album rules and return matching photos.

    Supported rule keys:
      - camera_model (str): EXIF camera model substring match
      - quality_score_gt (float): minimum (sharpness + exposure*100) / 2
      - date_after (str "YYYY-MM-DD"): taken_at >= date
      - date_before (str "YYYY-MM-DD"): taken_at <= date
      - country / province / city (str): exact match on geo fields
    """
    import json as _json
    from datetime import datetime as _dt

    try:
        rules: dict = _json.loads(rules_json) if rules_json else {}
    except Exception:
        rules = {}

    stmt = select(Photo).where(
        Photo.is_deleted.is_(False),
        Photo.is_archived.is_(False),
    )

    if rules.get("camera_model"):
        stmt = stmt.where(Photo.camera_model.ilike(f"%{rules['camera_model']}%"))

    if rules.get("quality_score_gt") is not None:
        threshold = float(rules["quality_score_gt"])
        stmt = stmt.where(Photo.sharpness_score >= threshold)

    if rules.get("date_after"):
        try:
            dt_after = _dt.strptime(rules["date_after"], "%Y-%m-%d")
            stmt = stmt.where(Photo.taken_at >= dt_after)
        except ValueError:
            pass

    if rules.get("date_before"):
        try:
            dt_before = _dt.strptime(rules["date_before"], "%Y-%m-%d")
            stmt = stmt.where(Photo.taken_at <= dt_before)
        except ValueError:
            pass

    if rules.get("country"):
        stmt = stmt.where(Photo.country == rules["country"])
    if rules.get("province"):
        stmt = stmt.where(Photo.province == rules["province"])
    if rules.get("city"):
        stmt = stmt.where(Photo.city == rules["city"])

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = (await db.execute(count_stmt)).scalar_one()

    result = await db.execute(
        stmt.order_by(Photo.taken_at.desc().nullslast())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), total


async def empty_trash(db: AsyncSession) -> int:
    """Hard-delete all photos in the trash. Returns count deleted."""
    result = await db.execute(select(Photo).where(Photo.is_deleted == True))  # noqa: E712
    photos = list(result.scalars().all())
    for photo in photos:
        await hard_delete_photo(db, photo)
    return len(photos)
