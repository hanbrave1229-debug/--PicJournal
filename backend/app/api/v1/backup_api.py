"""
Backup API — endpoints for the mobile auto-backup client.

Two-layer dedup (see PROJECT_STATUS.md §P0):
  1. Client keeps its own ledger of already-backed-up assets (bandwidth saver).
  2. Server is the source of truth: every upload is hashed (MD5) and skipped
     if the digest already exists in the library — so re-installs / cleared
     ledgers can never create duplicates.

Endpoints:
  POST /backup/check    → given a list of MD5 checksums, return which already
                          exist, so the client can skip uploading them.
  POST /backup/upload   → upload files; each is hashed and saved only if new.
                          A single scan is triggered afterwards to ingest them.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.import_api import (
    ALLOWED_EXTS,
    MAX_UPLOAD_SIZE,
    _resolve_dest,
    _safe_dest_path,
    _trigger_scan,
)
from app.db.database import get_db
from app.models.photo import Photo

router = APIRouter()

# Phone backups land here: {library_root}/PicJournal/backup/
_BACKUP_SUBDIR = "backup"


# ── /backup/check ───────────────────────────────────────────────────────────────

class CheckRequest(BaseModel):
    checksums: list[str]


class CheckResponse(BaseModel):
    existing: list[str]   # checksums already in the library → client skips these
    missing: list[str]    # checksums to upload


@router.post("/check", response_model=CheckResponse, summary="批量查询哪些照片已备份(按MD5)")
async def check_backup(
    body: CheckRequest, db: AsyncSession = Depends(get_db)
) -> CheckResponse:
    """
    The client sends MD5 digests it computed locally; we return which ones the
    library already has so it can skip uploading those bytes entirely.
    """
    wanted = {c.lower() for c in body.checksums if c}
    if not wanted:
        return CheckResponse(existing=[], missing=[])

    rows = await db.execute(
        select(Photo.md5_hash).where(
            Photo.md5_hash.in_(wanted), Photo.is_deleted.is_(False)
        )
    )
    existing = {r[0].lower() for r in rows.all() if r[0]}
    missing = [c for c in body.checksums if c and c.lower() not in existing]
    return CheckResponse(existing=sorted(existing), missing=missing)


# ── /backup/upload ──────────────────────────────────────────────────────────────

@router.post("/upload", summary="上传备份照片(服务端MD5兜底去重)")
async def upload_backup(
    files: list[UploadFile] = File(..., description="一次最多 100 个文件"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Save each uploaded file only if its MD5 is new to the library. After saving
    the new files, trigger a single scan so they are ingested (thumbnails, EXIF,
    taken_at, etc.). Returns per-file outcome counts.
    """
    if not files:
        raise HTTPException(status_code=422, detail="No files provided")
    if len(files) > 100:
        raise HTTPException(status_code=422, detail="Maximum 100 files per request")

    dest = _resolve_dest(None, _BACKUP_SUBDIR)

    saved = 0
    skipped_dup = 0
    skipped_bad: list[str] = []

    for upload in files:
        orig_name = Path(upload.filename or "file").name
        ext = Path(orig_name).suffix.lower()
        if ext not in ALLOWED_EXTS:
            skipped_bad.append(orig_name)
            await upload.close()
            continue

        try:
            content = await upload.read()
        except Exception:
            skipped_bad.append(orig_name)
            await upload.close()
            continue
        finally:
            await upload.close()

        if len(content) > MAX_UPLOAD_SIZE:
            skipped_bad.append(orig_name)
            continue

        md5 = hashlib.md5(content).hexdigest()

        # Server-side dedup: already in library → skip without writing.
        existing = await db.execute(
            select(Photo.id).where(
                Photo.md5_hash == md5, Photo.is_deleted.is_(False)
            ).limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            skipped_dup += 1
            continue

        try:
            target = _safe_dest_path(dest, orig_name)
            target.write_bytes(content)
            saved += 1
        except Exception:
            skipped_bad.append(orig_name)

    scan_task_id = None
    if saved:
        scan_task_id = await _trigger_scan(str(dest))

    return {
        "saved": saved,
        "skipped_duplicate": skipped_dup,
        "skipped_invalid": skipped_bad,
        "dest_path": str(dest),
        "scan_task_id": scan_task_id,
    }
