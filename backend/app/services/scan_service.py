"""
Scan service — creates ScanTask rows and launches background scan coroutines.
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import scanner, ai_tagger
from app.services import scoring_service
from app.db.database import AsyncSessionLocal
from app.models.scan_task import ScanStatus, ScanTask
from app.models.photo import Photo
from app.services.config_service import get_config

logger = logging.getLogger(__name__)


async def _run_geocoding(force: bool = False) -> None:
    """
    Batch-geocode photos that have GPS coordinates.

    - force=False (default): only photos with no city yet. Runs after each scan.
    - force=True: re-geocode ALL GPS photos, overwriting existing values. Use
      this after rebuilding the GeoNames DB (e.g. to pick up new Chinese names).

    Gracefully skips if the GeoNames DB is absent.
    """
    from app.services.geocoder import get_geocoder

    geocoder = get_geocoder()
    if not geocoder._ensure_connection():
        logger.info("geocoding: GeoNames DB not available — skipping (run scripts/build_geo_db.py)")
        return

    BATCH = 500
    try:
        total_geocoded = 0
        cursor = 0  # last processed photo id (force mode pages by id)
        while True:
            async with AsyncSessionLocal() as geo_db:
                q = (
                    select(Photo)
                    .where(
                        Photo.is_deleted.is_(False),
                        Photo.gps_lat.is_not(None),
                        Photo.gps_lon.is_not(None),
                    )
                    .order_by(Photo.id.asc())
                    .limit(BATCH)
                )
                if force:
                    q = q.where(Photo.id > cursor)        # page through all photos
                else:
                    q = q.where(Photo.city.is_(None))     # only un-geocoded photos

                photos = list((await geo_db.execute(q)).scalars().all())
                if not photos:
                    break

                geocoded = 0
                for photo in photos:
                    cursor = photo.id
                    if photo.gps_lat is None or photo.gps_lon is None:
                        continue
                    geo = geocoder.reverse(photo.gps_lat, photo.gps_lon)
                    if geo:
                        photo.country  = geo["country"]
                        photo.province = geo["province"]
                        photo.city     = geo["city"]
                        geocoded += 1

                await geo_db.commit()
                total_geocoded += geocoded

            # Non-force mode processes a single batch then exits (legacy behaviour);
            # force mode loops until all GPS photos are paged through.
            if not force:
                break

        logger.info("geocoding: completed, %d photos updated (force=%s)", total_geocoded, force)

    except Exception:
        logger.exception("geocoding: unexpected error")


async def _scan_then_auto_tag(task_id: int, scan_path: str) -> None:
    """
    Run the scan pipeline, then:
      Step 2 — offline reverse geocoding for GPS photos
      Step 3 — AI batch tagging (if ai_auto_tag is enabled)
    """
    # Step 1: scan
    await scanner.run_scan(
        task_id=task_id,
        scan_path=scan_path,
        db_session_factory=AsyncSessionLocal,
    )

    # Step 2: offline geocoding (always, no config needed — graceful no-op if DB absent)
    try:
        await _run_geocoding()
    except Exception:
        logger.exception("geocoding: pipeline error")

    # Step 2b: quality scoring — score any photos missing sharpness/exposure scores
    try:
        progress = await scoring_service.run_scoring(scan_task_id=task_id, force=False)
        if progress.total > 0:
            logger.info(
                "scoring: scored %d photos (%.1f%% complete)",
                progress.processed, progress.pct,
            )
    except Exception:
        logger.exception("scoring: post-scan scoring error")

    # Step 3: check whether auto-tag is on
    try:
        async with AsyncSessionLocal() as cfg_db:
            cfg = await get_config(cfg_db)
            if not cfg.ai_auto_tag:
                return
            if not cfg.ai_api_key:
                logger.info("auto_tag: skipped — AI API key not configured")
                return
            if ai_tagger.progress.running:
                logger.info("auto_tag: skipped — tagging already in progress")
                return

            api_key  = cfg.ai_api_key
            base_url = cfg.ai_base_url or ""
            model    = cfg.ai_model or "gpt-4o-mini"
            concurrency = getattr(cfg, "vlm_concurrency", 1) or 1

        # Step 4: fetch untagged photos in a fresh session and run tagging
        async with AsyncSessionLocal() as tag_db:
            result = await tag_db.execute(
                select(Photo)
                .where(Photo.is_deleted == False)  # noqa: E712
                .where(Photo.ai_caption.is_(None))
                .limit(200)
            )
            photos = list(result.scalars().all())

        if not photos:
            logger.info("auto_tag: no untagged photos found after scan")
            return

        logger.info("auto_tag: tagging %d photos after scan", len(photos))
        # run_batch_tagging opens its own per-task sessions (concurrency-safe).
        await ai_tagger.run_batch_tagging(
            photos, api_key, base_url, model, concurrency=concurrency,
        )

    except Exception:
        logger.exception("auto_tag: unexpected error during post-scan tagging")


async def create_and_start_scan(
    scan_path: str,
    db: AsyncSession,
) -> ScanTask:
    """
    Persist a new ScanTask row, then fire-and-forget the scan + optional
    auto-tag pipeline.

    The scan runs as a plain asyncio Task (not a BackgroundTask) so progress
    events can be streamed over WebSocket even after the HTTP response is sent.
    """
    task = ScanTask(
        scan_path=scan_path,
        status=ScanStatus.PENDING,
        created_at=datetime.utcnow(),
    )
    db.add(task)
    await db.flush()          # Populate task.id without committing
    await db.commit()
    await db.refresh(task)

    # Launch the async pipeline — runs concurrently with the event loop
    asyncio.create_task(
        _scan_then_auto_tag(task.id, scan_path),
        name=f"scan-{task.id}",
    )

    return task


async def get_scan_task(task_id: int, db: AsyncSession) -> ScanTask | None:
    result = await db.execute(select(ScanTask).where(ScanTask.id == task_id))
    return result.scalar_one_or_none()


async def list_scan_tasks(db: AsyncSession) -> list[ScanTask]:
    result = await db.execute(select(ScanTask).order_by(ScanTask.created_at.desc()))
    return list(result.scalars().all())


# ── Periodic auto-scan ──────────────────────────────────────────────────────

async def _resolve_auto_scan_path() -> str:
    """Path to scan automatically: the most recently scanned path, else the
    configured photos root (covers the whole library since scan is recursive)."""
    async with AsyncSessionLocal() as db:
        latest = (
            await db.execute(
                select(ScanTask).order_by(ScanTask.created_at.desc()).limit(1)
            )
        ).scalar_one_or_none()
    if latest and latest.scan_path:
        return latest.scan_path
    from app.config import get_settings
    return get_settings().photos_root


async def _is_scan_active() -> bool:
    """True if a scan is currently pending or running (avoid overlap)."""
    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(
                select(ScanTask)
                .where(ScanTask.status.in_([ScanStatus.PENDING, ScanStatus.RUNNING]))
                .limit(1)
            )
        ).scalar_one_or_none()
    return row is not None


async def run_auto_scan_loop() -> None:
    """
    Background loop that periodically scans the library for new files.

    Reads the interval/enabled flag from AppConfig each tick, so settings
    changes take effect without a restart. Incremental scan skips already
    imported files, so re-scanning is cheap. Skips a tick if a scan is already
    running. The heavy AI tagging step only runs if ai_auto_tag is enabled
    (same behaviour as a manual scan).
    """
    from pathlib import Path

    # Let startup (DB init, migrations) settle before the first tick.
    await asyncio.sleep(60)

    while True:
        interval = 30
        try:
            async with AsyncSessionLocal() as db:
                cfg = await get_config(db)
                enabled = cfg.auto_scan_enabled
                interval = max(5, cfg.auto_scan_interval_minutes or 30)

            if enabled:
                if await _is_scan_active():
                    logger.info("auto-scan: a scan is already active — skipping this tick")
                else:
                    path = await _resolve_auto_scan_path()
                    if path and Path(path).exists():
                        logger.info("auto-scan: triggering incremental scan of %s", path)
                        async with AsyncSessionLocal() as db:
                            await create_and_start_scan(path, db)
                    else:
                        logger.warning("auto-scan: scan path not found, skipping: %s", path)
        except Exception:
            logger.exception("auto-scan: loop iteration failed")

        await asyncio.sleep(interval * 60)


# asyncio imported here to avoid circular import at module load time
import asyncio  # noqa: E402
