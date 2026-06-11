"""
Dashboard API — aggregated statistics for the home page.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.photo_service import get_dashboard_stats

router = APIRouter()


@router.get("/stats", summary="Get dashboard statistics")
async def get_stats(db: AsyncSession = Depends(get_db)) -> dict:
    """
    Return aggregated stats:
      - total_photos, total_size_bytes
      - duplicate_count, reclaimable_bytes
      - blurry_count, underexposed_count, overexposed_count
      - last_scan_at, last_scan_path
    """
    return await get_dashboard_stats(db)
