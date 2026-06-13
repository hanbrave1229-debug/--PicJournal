"""
XMP 双向同步 API — P2

POST /xmp-sync/export          DB → XMP  (全量写出)
POST /xmp-sync/import          XMP → DB  (冲突解析: 以文件 mtime 为准)
GET  /xmp-sync/conflicts       列出 DB 与 XMP 不一致的照片

冲突解析策略
─────────────
• 扫描时读 XMP（只填 NULL 字段）——已在 scanner.py 实现
• AI 打标后写 XMP ——已在 ai_tagger.py / vision_api.py 实现
• /xmp-sync/import : XMP mtime > photo.updated_at → XMP 覆盖 DB（外部编辑优先）
• /xmp-sync/export : DB ai_caption/ai_tags → 写 XMP（DB 覆盖 XMP）
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.photo import Photo

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class SyncResult(BaseModel):
    processed: int
    updated: int
    skipped: int
    errors: int


class ConflictItem(BaseModel):
    photo_id: int
    file_path: str
    db_caption: str | None
    xmp_caption: str | None
    db_tags: list[str]
    xmp_tags: list[str]
    xmp_mtime: float | None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _run_sync(fn, *args):
    """Run a sync callable in the default executor."""
    return asyncio.get_running_loop().run_in_executor(None, fn, *args)


# ── Export: DB → XMP ───────────────────────────────────────────────────────────

@router.post("/export", response_model=SyncResult, summary="将 DB 中 AI 标签全量写出到 XMP")
async def export_to_xmp(db: AsyncSession = Depends(get_db)) -> SyncResult:
    """
    遍历所有有 ai_caption 或 ai_tags 的照片，
    写（或更新）对应的 .xmp sidecar 文件。
    """
    from app.services.xmp_service import write_sidecar

    result = await db.execute(
        select(Photo).where(
            Photo.is_deleted.is_(False),
            (Photo.ai_caption.is_not(None)) | (Photo.ai_tags.is_not(None)),
        )
    )
    photos = result.scalars().all()

    processed = updated = skipped = errors = 0

    def _write_one(photo: Photo) -> bool:
        tags = json.loads(photo.ai_tags) if photo.ai_tags else []
        try:
            write_sidecar(
                photo.file_path,
                description=photo.ai_caption,
                tags=tags,
            )
            return True
        except Exception as exc:
            logger.warning("XMP export failed photo id=%s: %s", photo.id, exc)
            return False

    for photo in photos:
        processed += 1
        if not Path(photo.file_path).exists():
            skipped += 1
            continue
        ok = await asyncio.get_running_loop().run_in_executor(None, _write_one, photo)
        if ok:
            updated += 1
        else:
            errors += 1

    return SyncResult(processed=processed, updated=updated, skipped=skipped, errors=errors)


# ── Import: XMP → DB (conflict: XMP mtime wins) ───────────────────────────────

@router.post("/import", response_model=SyncResult, summary="从 XMP 导入数据到 DB，以 mtime 为准")
async def import_from_xmp(db: AsyncSession = Depends(get_db)) -> SyncResult:
    """
    遍历所有照片，若对应 .xmp sidecar 的 mtime 新于 photo.updated_at，
    则用 XMP 的 description / tags 覆盖 DB。
    """
    from app.services.xmp_service import find_sidecar, read_sidecar

    result = await db.execute(
        select(Photo).where(Photo.is_deleted.is_(False))
    )
    photos = result.scalars().all()

    processed = updated = skipped = errors = 0

    for photo in photos:
        processed += 1
        try:
            def _check(file_path=photo.file_path, updated_at=photo.updated_at):
                sp = find_sidecar(file_path)
                if sp is None:
                    return None
                xmp_mtime = sp.stat().st_mtime
                # Compare mtime with updated_at (naive UTC)
                import datetime
                ua_ts = updated_at.timestamp() if updated_at else 0
                if xmp_mtime <= ua_ts:
                    return None  # DB is newer or equal, skip
                return read_sidecar(file_path)

            xmp = await asyncio.get_running_loop().run_in_executor(None, _check)
            if xmp is None:
                skipped += 1
                continue

            changed = False
            if xmp.description and xmp.description != photo.ai_caption:
                photo.ai_caption = xmp.description
                changed = True
            if xmp.tags:
                db_tags_str = json.dumps(xmp.tags, ensure_ascii=False)
                if db_tags_str != photo.ai_tags:
                    photo.ai_tags = db_tags_str
                    changed = True

            if changed:
                db.add(photo)
                updated += 1
            else:
                skipped += 1
        except Exception as exc:
            logger.warning("XMP import failed photo id=%s: %s", photo.id, exc)
            errors += 1

    await db.commit()
    return SyncResult(processed=processed, updated=updated, skipped=skipped, errors=errors)


# ── Conflicts list ─────────────────────────────────────────────────────────────

@router.get("/conflicts", summary="列出 DB 与 XMP 内容不一致的照片")
async def list_conflicts(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[ConflictItem]:
    """
    返回 XMP sidecar 存在且内容与 DB 不一致的照片列表（最多 limit 条）。
    用于在前端提示用户手动确认哪侧数据更权威。
    """
    from app.services.xmp_service import find_sidecar, read_sidecar

    result = await db.execute(
        select(Photo).where(Photo.is_deleted.is_(False)).limit(limit * 10)
    )
    photos = result.scalars().all()

    conflicts: list[ConflictItem] = []

    for photo in photos:
        if len(conflicts) >= limit:
            break
        try:
            def _read(fp=photo.file_path):
                sp = find_sidecar(fp)
                if sp is None:
                    return None, None
                mtime = sp.stat().st_mtime
                return read_sidecar(fp), mtime

            xmp, mtime = await asyncio.get_running_loop().run_in_executor(None, _read)
            if xmp is None:
                continue

            db_tags = json.loads(photo.ai_tags) if photo.ai_tags else []
            xmp_tags = xmp.tags or []

            caption_diff = xmp.description and xmp.description != photo.ai_caption
            tags_diff = sorted(xmp_tags) != sorted(db_tags)

            if caption_diff or tags_diff:
                conflicts.append(ConflictItem(
                    photo_id=photo.id,
                    file_path=photo.file_path,
                    db_caption=photo.ai_caption,
                    xmp_caption=xmp.description,
                    db_tags=db_tags,
                    xmp_tags=xmp_tags,
                    xmp_mtime=mtime,
                ))
        except Exception:
            continue

    return conflicts
