"""
Scan service — creates ScanTask rows and launches background scan coroutines.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import scanner
from app.db.database import AsyncSessionLocal
from app.models.scan_task import ScanStatus, ScanTask


async def create_and_start_scan(
    scan_path: str,
    db: AsyncSession,
) -> ScanTask:
    """
    Persist a new ScanTask row, then fire-and-forget the scan coroutine.

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

    # Launch the async scan — runs concurrently with the event loop
    asyncio.create_task(
        scanner.run_scan(
            task_id=task.id,
            scan_path=scan_path,
            db_session_factory=AsyncSessionLocal,
        ),
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
