"""
Scan service — creates ScanTask rows and launches background scan coroutines.
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import scanner, ai_tagger
from app.db.database import AsyncSessionLocal
from app.models.scan_task import ScanStatus, ScanTask
from app.models.photo import Photo
from app.services.config_service import get_config

logger = logging.getLogger(__name__)


async def _run_geocoding() -> None:
    """
    Batch-geocode photos that have GPS coordinates but no city yet.
    Runs after each scan — gracefully skips if the GeoNames DB is absent.
    """
    from app.services.geocoder import get_geocoder

    geocoder = get_geocoder()
    if not geocoder._ensure_connection():
        logger.info("geocoding: GeoNames DB not available — skipping (run scripts/build_geo_db.py)")
        return

    try:
        async with AsyncSessionLocal() as geo_db:
            result = await geo_db.execute(
                select(Photo)
                .where(
                    Photo.is_deleted.is_(False),
                    Photo.gps_lat.is_not(None),
                    Photo.gps_lon.is_not(None),
                    Photo.city.is_(None),        # only un-geocoded photos
                )
                .limit(500)
            )
            photos = list(result.scalars().all())

        if not photos:
            logger.info("geocoding: all GPS photos already geocoded")
            return

        logger.info("geocoding: processing %d photos", len(photos))
        geocoded = 0

        async with AsyncSessionLocal() as geo_db:
            result = await geo_db.execute(
                select(Photo).where(Photo.id.in_([p.id for p in photos]))
            )
            fresh = list(result.scalars().all())

            for photo in fresh:
                if photo.gps_lat is None or photo.gps_lon is None:
                    continue
                geo = geocoder.reverse(photo.gps_lat, photo.gps_lon)
                if geo:
                    photo.country  = geo["country"]
                    photo.province = geo["province"]
                    photo.city     = geo["city"]
                    geocoded += 1

            await geo_db.commit()

        logger.info("geocoding: completed %d / %d photos", geocoded, len(photos))

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
        async with AsyncSessionLocal() as tag_db:
            result = await tag_db.execute(
                select(Photo).where(Photo.id.in_([p.id for p in photos]))
            )
            fresh_photos = list(result.scalars().all())
            await ai_tagger.run_batch_tagging(fresh_photos, tag_db, api_key, base_url, model)

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


# asyncio imported here to avoid circular import at module load time
import asyncio  # noqa: E402
