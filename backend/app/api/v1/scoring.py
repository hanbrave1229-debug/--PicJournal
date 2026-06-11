"""
Scoring API — trigger OpenCV-based image quality scoring.

Endpoints:
  POST /api/v1/scoring/run              → batch-score all un-scored photos (background)
  POST /api/v1/scoring/run/sync         → batch-score synchronously (dev / small sets)
  POST /api/v1/scoring/run/{photo_id}   → score a single photo
  GET  /api/v1/scoring/stats            → quality breakdown counts
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services import scoring_service

router = APIRouter()


# ── Batch scoring ─────────────────────────────────────────────────────────────

@router.post("/run", summary="Score all un-scored photos (background)")
async def run_scoring(
    background_tasks: BackgroundTasks,
    scan_task_id: int | None = None,
    force: bool = False,
) -> dict:
    """
    Launch a background batch-scoring job.

    - scan_task_id: limit to photos from one scan task (None = whole library).
    - force: re-score photos that already have scores.

    Returns immediately; scoring runs asynchronously.
    """
    background_tasks.add_task(scoring_service.run_scoring, scan_task_id, force)
    return {
        "message": "Scoring job started",
        "scan_task_id": scan_task_id,
        "force": force,
    }


@router.post("/run/sync", summary="Score photos synchronously (small libraries / dev)")
async def run_scoring_sync(
    scan_task_id: int | None = None,
    force: bool = False,
) -> dict:
    """
    Same as /run but blocks until completion and returns a summary.
    """
    progress = await scoring_service.run_scoring(scan_task_id, force)
    return {
        "total": progress.total,
        "processed": progress.processed,
        "skipped": progress.skipped,
        "pct": progress.pct,
    }


# ── Single-photo scoring ──────────────────────────────────────────────────────

@router.post("/run/{photo_id}", summary="Score a single photo")
async def score_single_photo(
    photo_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Compute and persist quality scores for one photo.
    Useful for on-demand scoring triggered from the UI.
    """
    result = await scoring_service.score_one(photo_id)

    if result is None:
        raise HTTPException(status_code=404, detail=f"Photo {photo_id} not found")

    return {
        "photo_id": result.photo_id,
        "sharpness_score": result.sharpness_score,
        "exposure_score": result.exposure_score,
    }


# ── Quality stats ─────────────────────────────────────────────────────────────

@router.get("/stats", summary="Get quality score breakdown")
async def scoring_stats(db: AsyncSession = Depends(get_db)) -> dict:
    """
    Return counts of photos by quality category:
      - scored / unscored
      - blurry (sharpness < 80)
      - underexposed (exposure < 0.05)
      - overexposed (exposure > 0.95)
      - normal
    """
    from sqlalchemy import case, func, select
    from app.models.photo import Photo

    agg = await db.execute(
        select(
            func.count(Photo.id).label("total"),
            func.count(
                case((Photo.sharpness_score.is_not(None), 1))
            ).label("scored"),
            func.count(
                case((Photo.sharpness_score < 80, 1))
            ).label("blurry"),
            func.count(
                case((Photo.exposure_score < 0.05, 1))
            ).label("underexposed"),
            func.count(
                case((Photo.exposure_score > 0.95, 1))
            ).label("overexposed"),
        ).where(Photo.is_deleted.is_(False))
    )

    row = agg.one()
    total: int = row.total
    scored: int = row.scored
    blurry: int = row.blurry
    underexposed: int = row.underexposed
    overexposed: int = row.overexposed

    return {
        "total": total,
        "scored": scored,
        "unscored": total - scored,
        "blurry": blurry,
        "underexposed": underexposed,
        "overexposed": overexposed,
        "normal": max(0, scored - blurry - underexposed - overexposed),
    }
