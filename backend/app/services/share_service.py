"""
Share maintenance — periodic cleanup of expired album share links.

Expiry is already enforced at access time (the public endpoints return 410 for
expired links). This loop just keeps the table tidy by deleting rows whose
expires_at has passed, so old links don't accumulate forever.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import delete

from app.db.database import AsyncSessionLocal
from app.models.share import AlbumShare

logger = logging.getLogger(__name__)

# Run once a day.
_CLEANUP_INTERVAL_SECONDS = 24 * 3600


async def purge_expired_shares() -> int:
    """Delete share links whose expires_at is in the past. Returns rows removed."""
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            delete(AlbumShare).where(
                AlbumShare.expires_at.is_not(None),
                AlbumShare.expires_at < now,
            )
        )
        await db.commit()
        return result.rowcount or 0


async def run_share_cleanup_loop() -> None:
    """Periodically purge expired shares (daily). Launched from the app lifespan."""
    await asyncio.sleep(120)  # let startup settle first
    while True:
        try:
            removed = await purge_expired_shares()
            if removed:
                logger.info("share cleanup: removed %d expired share link(s)", removed)
        except Exception:
            logger.exception("share cleanup: loop iteration failed")
        await asyncio.sleep(_CLEANUP_INTERVAL_SECONDS)
