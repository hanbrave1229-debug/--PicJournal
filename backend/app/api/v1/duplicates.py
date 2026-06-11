"""
Duplicates API — run dedup pipeline, list groups, resolve keep/delete decisions.

Endpoints:
  POST  /api/v1/duplicates/run          → trigger full dedup pipeline
  GET   /api/v1/duplicates              → list all duplicate groups
  GET   /api/v1/duplicates/{group_id}   → single group detail
  POST  /api/v1/duplicates/resolve      → apply keep/delete decisions
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.duplicate import DuplicateGroupResponse, ResolveRequest
from app.schemas.photo import PhotoResponse
from app.services import dedup_service

router = APIRouter()


# ── Run pipeline ──────────────────────────────────────────────────────────────

@router.post("/run", summary="Run the full dedup pipeline")
async def run_dedup(
    background_tasks: BackgroundTasks,
    scan_task_id: int | None = None,
) -> dict:
    """
    Trigger the three-pass dedup pipeline as a background task.

    Pass scan_task_id to scope the run to a single scan; omit to process
    the entire library.

    Returns immediately with a confirmation message.
    """
    background_tasks.add_task(dedup_service.run_and_persist_dedup, scan_task_id)
    return {
        "message": "Dedup pipeline started",
        "scan_task_id": scan_task_id,
    }


@router.post("/run/sync", summary="Run dedup pipeline synchronously (dev/small libraries)")
async def run_dedup_sync(scan_task_id: int | None = None) -> dict:
    """
    Same as /run but waits for completion and returns a summary.
    Useful for small libraries or scripted workflows.
    """
    summary = await dedup_service.run_and_persist_dedup(scan_task_id)
    return summary


# ── List & detail ─────────────────────────────────────────────────────────────

@router.get("", response_model=list[DuplicateGroupResponse], summary="List all duplicate groups")
async def list_duplicate_groups(
    db: AsyncSession = Depends(get_db),
) -> list[DuplicateGroupResponse]:
    """
    Return all detected duplicate groups with their photos.
    Groups are ordered by type (exact → similar → burst) then by id.
    """
    groups = await dedup_service.list_duplicate_groups(db)
    return [
        DuplicateGroupResponse(
            id=g.id,
            group_type=g.group_type,
            recommended_keep_id=g.recommended_keep_id,
            photos=[PhotoResponse.from_orm(p) for p in g.photos],
        )
        for g in groups
    ]


@router.get(
    "/{group_id}",
    response_model=DuplicateGroupResponse,
    summary="Get single duplicate group detail",
)
async def get_duplicate_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
) -> DuplicateGroupResponse:
    group = await dedup_service.get_duplicate_group(group_id, db)
    if group is None:
        raise HTTPException(status_code=404, detail=f"Duplicate group {group_id} not found")
    return DuplicateGroupResponse(
        id=group.id,
        group_type=group.group_type,
        recommended_keep_id=group.recommended_keep_id,
        photos=[PhotoResponse.from_orm(p) for p in group.photos],
    )


# ── Resolve ───────────────────────────────────────────────────────────────────

@router.post("/resolve", summary="Resolve a duplicate group")
async def resolve_duplicate_group(
    payload: ResolveRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Apply keep/delete decisions for one duplicate group.

    - Photos in keep_ids   → marked as kept, unlinked from the group.
    - Photos in delete_ids → soft-deleted (is_deleted = True).

    Deletion is safe: no physical files are removed.
    """
    # Validate no overlap
    overlap = set(payload.keep_ids) & set(payload.delete_ids)
    if overlap:
        raise HTTPException(
            status_code=400,
            detail=f"Photo IDs appear in both keep and delete lists: {overlap}",
        )

    result = await dedup_service.resolve_group(
        group_id=payload.group_id,
        keep_ids=payload.keep_ids,
        delete_ids=payload.delete_ids,
        db=db,
    )

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result
