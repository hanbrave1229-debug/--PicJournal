"""
Dedup service — orchestrates the dedup pipeline and persists results to the DB.

Responsibilities:
  - Run run_dedup_pipeline() from the engine.
  - Clear stale DuplicateGroup rows before writing fresh ones.
  - Write new DuplicateGroup rows and link Photo.duplicate_group_id.
  - Apply the smart-keep recommendation and expose it on the group.
  - Execute a resolve action (keep/delete decisions from the UI).
"""
from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dedup_engine import DedupResult, _recommend_keep, run_dedup_pipeline
from app.db.database import AsyncSessionLocal
from app.models.duplicate_group import DuplicateGroup, DuplicateType
from app.models.photo import Photo


# ── Run & persist ─────────────────────────────────────────────────────────────

async def run_and_persist_dedup(scan_task_id: int | None = None) -> dict:
    """
    Execute the full dedup pipeline and write results to SQLite.

    Returns a summary dict:
      { "exact": int, "similar": int, "burst": int, "total_groups": int }
    """
    result: DedupResult = await run_dedup_pipeline(
        db_session_factory=AsyncSessionLocal,
        scan_task_id=scan_task_id,
    )

    groups_to_write = [
        (result.exact_groups, DuplicateType.EXACT),
        (result.similar_groups, DuplicateType.SIMILAR),
        (result.burst_groups, DuplicateType.BURST),
    ]

    async with AsyncSessionLocal() as session:
        # ── Clear previous dedup data (scoped to task if provided) ────────────
        if scan_task_id is not None:
            # Unlink photos first
            await session.execute(
                update(Photo)
                .where(Photo.scan_task_id == scan_task_id)
                .values(duplicate_group_id=None)
            )
        else:
            await session.execute(update(Photo).values(duplicate_group_id=None))
            await session.execute(delete(DuplicateGroup))

        await session.flush()

        # ── Write new groups ──────────────────────────────────────────────────
        counts = {DuplicateType.EXACT: 0, DuplicateType.SIMILAR: 0, DuplicateType.BURST: 0}

        for groups, dtype in groups_to_write:
            for photo_list in groups:
                if len(photo_list) < 2:
                    continue

                keep_id = _recommend_keep(photo_list)
                group = DuplicateGroup(
                    group_type=dtype,
                    recommended_keep_id=keep_id,
                )
                session.add(group)
                await session.flush()  # Get group.id

                # Link each photo to this group
                photo_ids = [p.id for p in photo_list]
                await session.execute(
                    update(Photo)
                    .where(Photo.id.in_(photo_ids))
                    .values(duplicate_group_id=group.id)
                )
                counts[dtype] += 1

        await session.commit()

    return {
        "exact": counts[DuplicateType.EXACT],
        "similar": counts[DuplicateType.SIMILAR],
        "burst": counts[DuplicateType.BURST],
        "total_groups": sum(counts.values()),
    }


# ── Query ─────────────────────────────────────────────────────────────────────

async def list_duplicate_groups(db: AsyncSession) -> list[DuplicateGroup]:
    """Return all DuplicateGroup rows with their photos eagerly loaded."""
    result = await db.execute(
        select(DuplicateGroup).order_by(DuplicateGroup.group_type, DuplicateGroup.id)
    )
    return list(result.scalars().all())


async def get_duplicate_group(group_id: int, db: AsyncSession) -> DuplicateGroup | None:
    result = await db.execute(
        select(DuplicateGroup).where(DuplicateGroup.id == group_id)
    )
    return result.scalar_one_or_none()


# ── Resolve ───────────────────────────────────────────────────────────────────

async def resolve_group(
    group_id: int,
    keep_ids: list[int],
    delete_ids: list[int],
    db: AsyncSession,
) -> dict:
    """
    Apply keep/delete decisions for a single duplicate group.

    - Photos in keep_ids   → is_deleted = False, duplicate_group_id = None
    - Photos in delete_ids → is_deleted = True  (soft delete only)
    - If all members are resolved, the group row is deleted.
    """
    group = await get_duplicate_group(group_id, db)
    if group is None:
        return {"error": f"Group {group_id} not found"}

    # Keep
    if keep_ids:
        await db.execute(
            update(Photo)
            .where(Photo.id.in_(keep_ids))
            .values(is_deleted=False, duplicate_group_id=None)
        )

    # Soft-delete
    if delete_ids:
        await db.execute(
            update(Photo)
            .where(Photo.id.in_(delete_ids))
            .values(is_deleted=True)
        )

    await db.flush()

    # If no non-deleted members remain in the group, clean up the group row
    remaining = await db.execute(
        select(Photo).where(
            Photo.duplicate_group_id == group_id,
            Photo.is_deleted.is_(False),
        )
    )
    if not remaining.scalars().first():
        await db.delete(group)

    await db.commit()

    return {
        "group_id": group_id,
        "kept": len(keep_ids),
        "deleted": len(delete_ids),
    }
