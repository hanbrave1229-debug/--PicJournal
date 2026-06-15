"""
Import API — ingest photos into the library and create albums from external sources.

Endpoints
---------
POST /import/photos          Upload photo files → save to {root}/PicJournal/{subdir}/ → scan
POST /import/album/zip       Upload a ZIP archive → extract → scan → create album
POST /import/album/from-library  Select existing photo IDs → create new album
GET  /import/scan-root       Return the detected library root (last scan path)
"""
from __future__ import annotations

import asyncio
import io
import shutil
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal, get_db
from app.models.scan_task import ScanTask, ScanStatus
from app.services import scan_service
from app.services import album_service

router = APIRouter()

# ── Constants ──────────────────────────────────────────────────────────────────

ALLOWED_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".heic", ".heif", ".bmp", ".tiff", ".tif",
    ".mp4", ".mov", ".avi",   # video passthrough (scanned but no thumb)
}
MAX_UPLOAD_SIZE = 500 * 1024 * 1024   # 500 MB per file
PICJOURNAL_FOLDER = "PicJournal"


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _get_library_root(db: AsyncSession) -> Path | None:
    """Return the directory used in the most recent completed scan."""
    result = await db.execute(
        select(ScanTask).order_by(ScanTask.id.desc()).limit(20)
    )
    tasks = result.scalars().all()
    for task in tasks:
        if task.scan_path:
            p = Path(task.scan_path)
            if p.exists():
                return p
    return None


def _resolve_dest(root: Path | None, subdir: str) -> Path:
    """
    Build writable destination directory for imported photos.
    Uses settings.import_dir (/app/data/imported/{subdir}) which is a
    writable Docker volume — avoids writing into the read-only /photos mount.
    """
    from app.config import get_settings as _gs
    import_base = Path(_gs().import_dir)
    safe_sub = Path(subdir.strip("/")).name or "imported"
    dest = import_base / safe_sub
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def _safe_dest_path(dest: Path, filename: str) -> Path:
    """Return a non-colliding path inside dest for the given filename."""
    target = dest / filename
    if not target.exists():
        return target
    stem, suffix = Path(filename).stem, Path(filename).suffix
    for i in range(1, 10000):
        candidate = dest / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
    return dest / f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"


async def _trigger_scan(scan_path: str) -> int:
    """Fire-and-forget scan on a directory; returns the new task ID."""
    async with AsyncSessionLocal() as db:
        task = await scan_service.create_and_start_scan(scan_path, db)
        return task.id


# ── GET scan root ──────────────────────────────────────────────────────────────

@router.get("/scan-root", summary="获取检测到的照片库根目录")
async def get_scan_root(db: AsyncSession = Depends(get_db)) -> dict:
    root = await _get_library_root(db)
    return {"root": str(root) if root else None}


# ── POST /import/photos ────────────────────────────────────────────────────────

@router.post("/photos", summary="上传照片文件到库，自动扫描入库")
async def import_photos(
    files: list[UploadFile] = File(..., description="一次最多 200 张"),
    subdir: str = Form("imported", description="目标子目录名称，写入 {根目录}/PicJournal/{subdir}/"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Accept photo uploads, write them to {library_root}/PicJournal/{subdir}/,
    then trigger an async scan on that directory so the photos appear in the library.

    Returns immediately with the scan task ID; poll /scan/status/{task_id} for progress.
    """
    if not files:
        raise HTTPException(status_code=422, detail="No files provided")
    if len(files) > 200:
        raise HTTPException(status_code=422, detail="Maximum 200 files per request")

    dest = _resolve_dest(None, subdir)

    saved: list[str] = []
    skipped: list[str] = []

    for upload in files:
        orig_name = Path(upload.filename or "file").name
        ext = Path(orig_name).suffix.lower()
        if ext not in ALLOWED_EXTS:
            skipped.append(orig_name)
            continue

        target = _safe_dest_path(dest, orig_name)
        try:
            content = await upload.read()
            if len(content) > MAX_UPLOAD_SIZE:
                skipped.append(orig_name)
                continue
            target.write_bytes(content)
            saved.append(target.name)
        except Exception:
            skipped.append(orig_name)
        finally:
            await upload.close()

    if not saved:
        raise HTTPException(status_code=422, detail=f"No valid photo files were saved. Skipped: {skipped}")

    task_id = await _trigger_scan(str(dest))

    return {
        "saved": len(saved),
        "skipped": skipped,
        "dest_path": str(dest),
        "scan_task_id": task_id,
    }


# ── POST /import/album/zip ─────────────────────────────────────────────────────

@router.post("/album/zip", summary="上传 ZIP 包，解压扫描后自动建相册")
async def import_album_from_zip(
    file: UploadFile = File(..., description="ZIP 文件（含照片，支持 Apple Photos 导出包）"),
    album_name: str = Form(..., description="新相册名称"),
    subdir: str = Form("", description="目标子目录（留空则使用相册名称）"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Extract a ZIP archive, save valid photo files to {root}/PicJournal/{subdir}/,
    trigger a scan, and create a new album linked to a pending scan.

    The album is created immediately (empty); photos are added once the scan
    completes via a background task.
    """
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=422, detail="File must be a .zip archive")

    effective_sub = subdir.strip() or album_name
    dest = _resolve_dest(None, effective_sub)

    content = await file.read()
    await file.close()

    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=422, detail="Invalid ZIP file")

    saved: list[str] = []
    skipped: list[str] = []

    for member in zf.infolist():
        if member.is_dir():
            continue
        member_path = Path(member.filename)
        # Skip macOS metadata files
        if member_path.name.startswith(".") or "__MACOSX" in member.filename:
            continue
        ext = member_path.suffix.lower()
        if ext not in ALLOWED_EXTS:
            skipped.append(member.filename)
            continue

        # Flatten to a single directory (ignore ZIP sub-folder structure)
        target = _safe_dest_path(dest, member_path.name)
        try:
            target.write_bytes(zf.read(member.filename))
            saved.append(target.name)
        except Exception:
            skipped.append(member.filename)

    zf.close()

    if not saved:
        raise HTTPException(status_code=422, detail=f"No valid photo files found in ZIP. Skipped: {skipped[:20]}")

    # Create the album eagerly so the user can see it right away
    album = await album_service.create_album(db, title=album_name)

    # Scan + auto-link photos to the album in the background
    asyncio.create_task(
        _scan_and_link_album(str(dest), album.id),
        name=f"import-album-{album.id}",
    )

    return {
        "album_id": album.id,
        "album_name": album_name,
        "saved": len(saved),
        "skipped": skipped[:20],
        "dest_path": str(dest),
        "status": "scan_started",
    }


async def _scan_and_link_album(scan_path: str, album_id: int) -> None:
    """Background: scan path then add all discovered photos to the album."""
    import asyncio as _a
    from app.models.photo import Photo
    from sqlalchemy import select as _select

    task_id = await _trigger_scan(scan_path)

    # Poll until the scan finishes (max 30 min)
    for _ in range(360):
        await _a.sleep(5)
        async with AsyncSessionLocal() as db:
            from app.models.scan_task import ScanTask as ST
            result = await db.execute(_select(ST).where(ST.id == task_id))
            task = result.scalar_one_or_none()
            if task and task.status in ("done", "failed", "completed"):
                break

    # Link newly scanned photos to the album
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            _select(Photo).where(
                Photo.is_deleted.is_(False),
                Photo.file_path.like(f"{scan_path}%"),
            )
        )
        photo_ids = [p.id for p in result.scalars().all()]
        if photo_ids:
            await album_service.add_photos_to_album(db, album_id, photo_ids)


# ── POST /import/album/{album_id}/zip — add ZIP to existing album ──────────────

@router.post("/album/{album_id}/zip", summary="上传 ZIP 包到已有相册，无需相册名")
async def import_zip_to_album(
    album_id: int,
    file: UploadFile = File(..., description="ZIP 文件"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Extract ZIP, save photos to {root}/PicJournal/album-{album_id}/,
    trigger scan, and link discovered photos to the existing album.
    Photos are sorted into library by taken_at as usual.
    """
    from app.models.album import Album
    album = await db.get(Album, album_id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=422, detail="File must be a .zip archive")

    dest = _resolve_dest(None, f"album-{album_id}")

    content = await file.read()
    await file.close()

    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=422, detail="Invalid ZIP file")

    saved: list[str] = []
    skipped: list[str] = []

    for member in zf.infolist():
        if member.is_dir():
            continue
        member_path = Path(member.filename)
        if member_path.name.startswith(".") or "__MACOSX" in member.filename:
            continue
        ext = member_path.suffix.lower()
        if ext not in ALLOWED_EXTS:
            skipped.append(member.filename)
            continue
        target = _safe_dest_path(dest, member_path.name)
        try:
            target.write_bytes(zf.read(member.filename))
            saved.append(target.name)
        except Exception:
            skipped.append(member.filename)

    zf.close()

    if not saved:
        raise HTTPException(status_code=422, detail=f"No valid photo files found in ZIP. Skipped: {skipped[:20]}")

    asyncio.create_task(
        _scan_and_link_album(str(dest), album_id),
        name=f"import-zip-album-{album_id}",
    )

    return {
        "album_id": album_id,
        "album_name": album.title,
        "saved": len(saved),
        "skipped": skipped[:20],
        "dest_path": str(dest),
        "status": "scan_started",
    }


# ── POST /import/album/from-library ───────────────────────────────────────────

class FromLibraryRequest(BaseModel):
    photo_ids: list[int]
    album_name: str


@router.post("/album/from-library", summary="从已有库中选择照片，创建新相册")
async def import_album_from_library(
    body: FromLibraryRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Create a new album and immediately add the given photo IDs.
    No file copying — photos stay in place.
    """
    if not body.photo_ids:
        raise HTTPException(status_code=422, detail="photo_ids must not be empty")
    if not body.album_name.strip():
        raise HTTPException(status_code=422, detail="album_name must not be empty")

    album = await album_service.create_album(db, title=body.album_name.strip())
    added = await album_service.add_photos_to_album(db, album.id, body.photo_ids)

    return {
        "album_id": album.id,
        "album_name": album.title,
        "added": added,
    }


@router.get("/history", summary="导入历史记录")
async def import_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Return paginated scan tasks that were triggered by import operations
    (scan_path starts with import_dir). Falls back to all scan tasks if
    import_dir is not configured.
    """
    from app.config import get_settings as _gs
    from sqlalchemy import func
    import_base = _gs().import_dir  # e.g. /app/data/imported

    stmt = (
        select(ScanTask)
        .where(ScanTask.scan_path.like(f"{import_base}%"))
        .order_by(desc(ScanTask.created_at))
    )
    total_stmt = select(func.count(ScanTask.id)).where(ScanTask.scan_path.like(f"{import_base}%"))

    total: int = (await db.execute(total_stmt)).scalar_one()
    rows = (await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": t.id,
                "scan_path": t.scan_path,
                "status": t.status,
                "total_files": t.total_files,
                "processed_files": t.processed_files,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "finished_at": t.finished_at.isoformat() if t.finished_at else None,
                "error_message": t.error_message,
            }
            for t in rows
        ],
    }
