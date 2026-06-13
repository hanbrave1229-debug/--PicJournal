"""
连拍堆叠服务 — pHash 相似照片自动分组
=======================================
算法：
  1. 取所有未删除照片（file_path + phash + taken_at + id）
  2. 按 taken_at 排序，用滑动窗口比较相邻照片 pHash Hamming 距离
  3. Hamming ≤ HAMMING_THRESHOLD 且 |Δt| ≤ TIME_GAP_SECONDS → 同一连拍组
  4. 每组分配一个新 UUID（stack_id），清晰度最高的设为封面

已有 phash 存储在 Photo.phash（imagehash 库的 64-bit hex 字符串）。
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, update

from app.db.database import AsyncSessionLocal
from app.models.photo import Photo

logger = logging.getLogger(__name__)

HAMMING_THRESHOLD  = 8     # Hamming 距离 ≤ 8 视为相似
TIME_GAP_SECONDS   = 30    # 拍摄时间差 ≤ 30s 视为同一连拍

# ── Public API ─────────────────────────────────────────────────────────────────

async def auto_stack(dry_run: bool = False) -> dict:
    """
    扫描全库，识别连拍组并写入 stack_id。
    幂等：已有 stack_id 的照片跳过（除非 reset=True）。
    Returns: {groups_created, photos_stacked, skipped}
    """
    rows = await _load_photos()
    groups = _find_groups(rows)

    groups_created  = 0
    photos_stacked  = 0

    if not dry_run:
        for group in groups:
            sid = str(uuid.uuid4())
            # 清晰度最高的作为封面
            cover_id = _pick_cover(group)
            async with AsyncSessionLocal() as session:
                for photo_id, *_ in group:
                    photo = await session.get(Photo, photo_id)
                    if photo and not photo.stack_id:
                        photo.stack_id      = sid
                        photo.is_stack_cover = (photo_id == cover_id)
                await session.commit()
            groups_created += 1
            photos_stacked += len(group)

    skipped = len(rows) - photos_stacked
    return {
        "groups_created": groups_created,
        "photos_stacked": photos_stacked,
        "skipped": skipped,
        "dry_run": dry_run,
    }


async def unstack(photo_id: int) -> bool:
    """从堆叠中移除指定照片（保持其他成员的 stack_id）。"""
    async with AsyncSessionLocal() as session:
        photo = await session.get(Photo, photo_id)
        if not photo:
            return False
        old_sid = photo.stack_id
        photo.stack_id      = None
        photo.is_stack_cover = False
        await session.commit()

        # 如果堆叠只剩1张了，解散堆叠
        if old_sid:
            remaining = (await session.execute(
                select(Photo).where(Photo.stack_id == old_sid)
            )).scalars().all()
            if len(remaining) == 1:
                remaining[0].stack_id      = None
                remaining[0].is_stack_cover = False
                await session.commit()
    return True


async def set_stack_cover(photo_id: int) -> bool:
    """将指定照片设为其堆叠的封面。"""
    async with AsyncSessionLocal() as session:
        photo = await session.get(Photo, photo_id)
        if not photo or not photo.stack_id:
            return False
        sid = photo.stack_id
        # 清除旧封面标记
        members = (await session.execute(
            select(Photo).where(Photo.stack_id == sid)
        )).scalars().all()
        for m in members:
            m.is_stack_cover = (m.id == photo_id)
        await session.commit()
    return True


async def dissolve_stack(stack_id: str) -> int:
    """解散整个堆叠，返回解散的照片数量。"""
    async with AsyncSessionLocal() as session:
        members = (await session.execute(
            select(Photo).where(Photo.stack_id == stack_id)
        )).scalars().all()
        count = len(members)
        for m in members:
            m.stack_id      = None
            m.is_stack_cover = False
        await session.commit()
    return count


async def get_stack(stack_id: str) -> list[dict]:
    """返回堆叠内所有照片（封面优先）。"""
    async with AsyncSessionLocal() as session:
        photos = (await session.execute(
            select(Photo)
            .where(Photo.stack_id == stack_id)
            .where(Photo.is_deleted.is_(False))
            .order_by(Photo.is_stack_cover.desc(), Photo.taken_at.asc())
        )).scalars().all()
    return [_photo_dict(p) for p in photos]


async def list_stack_covers() -> list[dict]:
    """返回所有堆叠的封面照片列表（Gallery 视图用）。"""
    async with AsyncSessionLocal() as session:
        photos = (await session.execute(
            select(Photo)
            .where(Photo.is_stack_cover.is_(True))
            .where(Photo.is_deleted.is_(False))
            .order_by(Photo.taken_at.desc().nullslast())
        )).scalars().all()
    return [_photo_dict(p) for p in photos]


# ── Internal: clustering ───────────────────────────────────────────────────────

async def _load_photos() -> list[tuple]:
    """Return (id, phash_hex, taken_at, sharpness_score) for all undeleted, unstacked photos."""
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(Photo.id, Photo.phash, Photo.taken_at, Photo.sharpness_score)
            .where(Photo.is_deleted.is_(False))
            .where(Photo.stack_id.is_(None))     # only unstacked photos
            .where(Photo.phash.isnot(None))
            .order_by(Photo.taken_at.asc().nullslast())
        )).all()
    return list(rows)


def _hamming(a: str, b: str) -> int:
    """Hamming distance between two hex pHash strings (imagehash format)."""
    try:
        ia, ib = int(a, 16), int(b, 16)
        xor = ia ^ ib
        return bin(xor).count("1")
    except (ValueError, TypeError):
        return 999


def _find_groups(rows: list[tuple]) -> list[list[tuple]]:
    """
    Sliding-window grouping:
    Compare consecutive rows (sorted by taken_at).
    Group rows where Hamming ≤ threshold AND Δt ≤ time_gap.
    Returns only groups with ≥ 2 photos.
    """
    if not rows:
        return []

    groups: list[list[tuple]] = []
    current: list[tuple] = [rows[0]]

    for i in range(1, len(rows)):
        prev = current[-1]
        curr = rows[i]

        ph_ok = _hamming(prev[1], curr[1]) <= HAMMING_THRESHOLD

        # Δt check
        t_prev: datetime | None = prev[2]
        t_curr: datetime | None = curr[2]
        if t_prev is not None and t_curr is not None:
            dt = abs((t_curr - t_prev).total_seconds())
            t_ok = dt <= TIME_GAP_SECONDS
        else:
            t_ok = ph_ok  # no time info: rely solely on visual hash

        if ph_ok and t_ok:
            current.append(curr)
        else:
            if len(current) >= 2:
                groups.append(current)
            current = [curr]

    if len(current) >= 2:
        groups.append(current)

    return groups


def _pick_cover(group: list[tuple]) -> int:
    """Pick the photo with the highest sharpness_score as the stack cover."""
    best_id, best_score = group[0][0], group[0][3] or 0.0
    for photo_id, _, _, score in group:
        if (score or 0.0) > best_score:
            best_id, best_score = photo_id, score
    return best_id


def _photo_dict(p: Photo) -> dict:
    return {
        "id":            p.id,
        "file_path":     p.file_path,
        "taken_at":      p.taken_at.isoformat() if p.taken_at else None,
        "thumbnail_256": p.thumbnail_256,
        "sharpness_score": p.sharpness_score,
        "is_stack_cover":  p.is_stack_cover,
        "stack_id":      p.stack_id,
    }
