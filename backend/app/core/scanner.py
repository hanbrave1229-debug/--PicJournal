"""
Async directory scanner.

Workflow per scan task:
  1. Recursively walk the target directory with asyncio (non-blocking).
  2. For each image file, run CPU-bound work (EXIF, image size) in a
     ProcessPoolExecutor to avoid GIL contention.
  3. Batch-upsert Photo rows into SQLite.
  4. Broadcast progress updates via an in-memory channel so the
     WebSocket endpoint can stream them to the browser.
"""
from __future__ import annotations

import asyncio
import os
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

import aiofiles.os

from app.config import get_settings
from app.core.exif_extractor import ExifData, extract as extract_exif

settings = get_settings()

# ── Progress broadcast ────────────────────────────────────────────────────────
# Maps task_id → set of asyncio.Queue instances (one per connected WebSocket).
_progress_queues: dict[int, set[asyncio.Queue[dict]]] = {}


def subscribe(task_id: int) -> asyncio.Queue[dict]:
    """Register a new WebSocket listener for *task_id*. Returns a Queue."""
    q: asyncio.Queue[dict] = asyncio.Queue(maxsize=64)
    _progress_queues.setdefault(task_id, set()).add(q)
    return q


def unsubscribe(task_id: int, q: asyncio.Queue[dict]) -> None:
    """Remove a WebSocket listener."""
    _progress_queues.get(task_id, set()).discard(q)


async def _broadcast(task_id: int, payload: dict) -> None:
    for q in list(_progress_queues.get(task_id, set())):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass  # Slow consumer — skip frame rather than block


# ── Per-file worker (runs in ProcessPoolExecutor) ─────────────────────────────

class FileInfo(NamedTuple):
    file_path: str
    file_name: str
    file_ext: str
    file_size: int
    width: int | None
    height: int | None
    taken_at: datetime | None
    camera_make: str | None
    camera_model: str | None
    aperture: str | None
    shutter_speed: str | None
    iso: int | None
    gps_lat: float | None
    gps_lon: float | None
    thumbhash: str | None  # Dominant color as "#RRGGBB" for progressive placeholder
    sharpness_score: float | None  # Laplacian variance — higher = sharper


def _process_file(file_path: str) -> FileInfo | None:
    """
    CPU-bound work executed in a child process:
      - Read image dimensions via Pillow (fast header-only open).
      - Extract EXIF via exifread.

    Returns None on any unrecoverable error (corrupt file, not an image, etc.).
    """
    try:
        from PIL import Image

        path = Path(file_path)
        stat = path.stat()

        # Load image to get dimensions + dominant color for ThumbHash placeholder
        sharpness_score: float | None = None
        with Image.open(path) as img:
            width, height = img.size
            # Compute dominant color: resize to 1×1 → #RRGGBB
            # Fast because Pillow uses box-average downsampling at this scale.
            try:
                tiny = img.convert("RGB").resize((1, 1), Image.LANCZOS)
                r, g, b = tiny.getpixel((0, 0))
                thumbhash: str | None = f"#{r:02x}{g:02x}{b:02x}"
            except Exception:
                thumbhash = None

            # Laplacian sharpness: variance of the Laplacian on a downsampled
            # grayscale — fast enough (target ≤256px), no cv2 required.
            try:
                import numpy as np
                gray = img.convert("L")
                # Downsample to max 256px on longest side for speed
                scale = min(256 / max(width, height), 1.0)
                if scale < 1.0:
                    gray = gray.resize(
                        (max(1, int(width * scale)), max(1, int(height * scale))),
                        Image.BILINEAR,
                    )
                arr = np.array(gray, dtype=np.float32)
                # Laplacian kernel convolution via numpy (avoids cv2 dependency)
                lap = (
                    arr[:-2, 1:-1]
                    + arr[2:, 1:-1]
                    + arr[1:-1, :-2]
                    + arr[1:-1, 2:]
                    - 4 * arr[1:-1, 1:-1]
                )
                sharpness_score = float(lap.var())
            except Exception:
                sharpness_score = None

        exif: ExifData = extract_exif(path)

        return FileInfo(
            file_path=file_path,
            file_name=path.name,
            file_ext=path.suffix.lower(),
            file_size=stat.st_size,
            width=width,
            height=height,
            taken_at=exif.taken_at,
            camera_make=exif.camera_make,
            camera_model=exif.camera_model,
            aperture=exif.aperture,
            shutter_speed=exif.shutter_speed,
            iso=exif.iso,
            gps_lat=exif.gps_lat,
            gps_lon=exif.gps_lon,
            thumbhash=thumbhash,
            sharpness_score=sharpness_score,
        )
    except Exception:
        return None


# ── Directory walker ──────────────────────────────────────────────────────────

async def _walk_images(root: str) -> list[str]:
    """
    Recursively collect all image file paths under *root*.
    Uses os.scandir via asyncio thread pool to stay non-blocking.
    """
    exts = set(settings.supported_extensions)
    found: list[str] = []

    loop = asyncio.get_running_loop()

    def _scan(directory: str) -> None:
        try:
            with os.scandir(directory) as it:
                for entry in it:
                    if entry.is_dir(follow_symlinks=False):
                        _scan(entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        if Path(entry.name).suffix.lower() in exts:
                            found.append(entry.path)
        except PermissionError:
            pass  # Skip unreadable directories

    await loop.run_in_executor(None, _scan, root)
    return found


# ── Batch DB upsert ───────────────────────────────────────────────────────────

async def _upsert_photos(
    db_session_factory,  # AsyncSessionLocal callable
    scan_task_id: int,
    batch: list[FileInfo],
) -> None:
    """Insert or update Photo rows for a batch of FileInfo objects."""
    from sqlalchemy import select
    from app.models.photo import Photo

    async with db_session_factory() as session:
        for info in batch:
            # Check if this path was already scanned
            result = await session.execute(
                select(Photo).where(Photo.file_path == info.file_path)
            )
            photo: Photo | None = result.scalar_one_or_none()

            if photo is None:
                photo = Photo(
                    file_path=info.file_path,
                    scan_task_id=scan_task_id,
                )

            # Always refresh mutable fields
            photo.file_name = info.file_name
            photo.file_ext = info.file_ext
            photo.file_size = info.file_size
            photo.width = info.width
            photo.height = info.height
            photo.taken_at = info.taken_at
            photo.camera_make = info.camera_make
            photo.camera_model = info.camera_model
            photo.aperture = info.aperture
            photo.shutter_speed = info.shutter_speed
            photo.iso = info.iso
            photo.gps_lat = info.gps_lat
            photo.gps_lon = info.gps_lon
            # Only write thumbhash when not yet computed (preserve any future upgrades)
            if photo.thumbhash is None and info.thumbhash is not None:
                photo.thumbhash = info.thumbhash
            # Sharpness quick estimate: only write if not yet scored by the
            # dedicated scoring pipeline (which uses cv2 and is more accurate).
            if photo.sharpness_score is None and info.sharpness_score is not None:
                photo.sharpness_score = info.sharpness_score

            session.add(photo)

        await session.commit()


# ── Main scan coroutine ───────────────────────────────────────────────────────

BATCH_SIZE = 50  # Photos committed to DB per batch


async def run_scan(
    task_id: int,
    scan_path: str,
    db_session_factory,
) -> None:
    """
    Full scan pipeline for a single ScanTask.

    This coroutine is meant to run as a FastAPI BackgroundTask.
    It updates the ScanTask row in the DB and broadcasts progress
    events to all subscribed WebSocket clients.
    """
    from sqlalchemy import select, update
    from app.models.scan_task import ScanTask, ScanStatus

    async def _update_task(**kwargs) -> None:
        async with db_session_factory() as session:
            await session.execute(
                update(ScanTask).where(ScanTask.id == task_id).values(**kwargs)
            )
            await session.commit()

    # ── Mark task as running ──────────────────────────────────────────────────
    await _update_task(status=ScanStatus.RUNNING, started_at=datetime.utcnow())
    await _broadcast(task_id, {"event": "started", "task_id": task_id})

    try:
        # ── Step 1: Walk directory ────────────────────────────────────────────
        await _broadcast(task_id, {"event": "walking", "path": scan_path})
        all_paths = await _walk_images(scan_path)
        total = len(all_paths)

        await _update_task(total_files=total)
        await _broadcast(task_id, {"event": "found", "total": total})

        if total == 0:
            await _update_task(
                status=ScanStatus.COMPLETED,
                finished_at=datetime.utcnow(),
                processed_files=0,
            )
            await _broadcast(task_id, {"event": "completed", "processed": 0, "total": 0})
            return

        # ── Step 2: Process files in parallel + batch-write ──────────────────
        processed = 0
        loop = asyncio.get_running_loop()

        with ProcessPoolExecutor(max_workers=settings.worker_processes) as pool:
            # Submit all files to the process pool in chunks to avoid
            # overwhelming memory with futures for 100k+ photos.
            chunk_size = BATCH_SIZE * 4

            for chunk_start in range(0, total, chunk_size):
                chunk = all_paths[chunk_start : chunk_start + chunk_size]

                # Fan out to process pool
                futures = [
                    loop.run_in_executor(pool, _process_file, path)
                    for path in chunk
                ]
                results = await asyncio.gather(*futures, return_exceptions=True)

                # Collect successful results into micro-batches for DB writes
                batch: list[FileInfo] = []
                for res in results:
                    if isinstance(res, FileInfo):
                        batch.append(res)
                    # None or Exception → silently skip corrupt/unreadable files

                    if len(batch) >= BATCH_SIZE:
                        await _upsert_photos(db_session_factory, task_id, batch)
                        batch.clear()

                if batch:
                    await _upsert_photos(db_session_factory, task_id, batch)

                processed += len(chunk)
                pct = round(processed / total * 100, 1)

                await _update_task(processed_files=processed)
                await _broadcast(
                    task_id,
                    {"event": "progress", "processed": processed, "total": total, "pct": pct},
                )

        # ── Done ─────────────────────────────────────────────────────────────
        await _update_task(
            status=ScanStatus.COMPLETED,
            finished_at=datetime.utcnow(),
            processed_files=processed,
        )
        await _broadcast(
            task_id,
            {"event": "completed", "processed": processed, "total": total},
        )

    except Exception as exc:
        await _update_task(
            status=ScanStatus.FAILED,
            finished_at=datetime.utcnow(),
            error_message=str(exc),
        )
        await _broadcast(task_id, {"event": "error", "message": str(exc)})
        raise
