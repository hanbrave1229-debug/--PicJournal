"""
Geocoding API — manually trigger offline reverse geocoding.

POST /geocoding/run        batch-geocode all un-geocoded GPS photos
POST /geocoding/{photo_id} geocode a single photo
GET  /geocoding/status     DB availability + pending count
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal, get_db
from app.models.photo import Photo
from app.services.geocoder import get_geocoder

router = APIRouter()


class GeoStatus(BaseModel):
    db_available: bool
    pending_count: int


class GeoResult(BaseModel):
    photo_id: int
    country: str | None
    province: str | None
    city: str | None


@router.get("/status", response_model=GeoStatus)
async def geo_status(db: AsyncSession = Depends(get_db)) -> GeoStatus:
    """Check GeoNames DB availability and number of un-geocoded GPS photos."""
    geocoder = get_geocoder()
    available = geocoder._ensure_connection()

    result = await db.execute(
        select(Photo).where(
            Photo.is_deleted.is_(False),
            Photo.gps_lat.is_not(None),
            Photo.city.is_(None),
        )
    )
    pending = len(result.scalars().all())

    return GeoStatus(db_available=available, pending_count=pending)


@router.post("/{photo_id}", response_model=GeoResult)
async def geocode_photo(
    photo_id: int,
    db: AsyncSession = Depends(get_db),
) -> GeoResult:
    """Geocode a single photo by ID."""
    result = await db.execute(
        select(Photo).where(Photo.id == photo_id, Photo.is_deleted.is_(False))
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    if photo.gps_lat is None or photo.gps_lon is None:
        raise HTTPException(status_code=422, detail="Photo has no GPS coordinates")

    geocoder = get_geocoder()
    if not geocoder._ensure_connection():
        raise HTTPException(
            status_code=503,
            detail="GeoNames DB not available. Run scripts/build_geo_db.py first.",
        )

    geo = geocoder.reverse(photo.gps_lat, photo.gps_lon)
    if geo:
        photo.country  = geo["country"]
        photo.province = geo["province"]
        photo.city     = geo["city"]
        await db.commit()
        await db.refresh(photo)

    return GeoResult(
        photo_id=photo.id,
        country=photo.country,
        province=photo.province,
        city=photo.city,
    )


@router.post("/run", status_code=202)
async def run_geocoding_batch() -> dict:
    """
    Fire-and-forget batch geocoding for all un-geocoded GPS photos.
    Returns immediately; geocoding runs in the background.
    """
    from app.services.scan_service import _run_geocoding

    asyncio.create_task(_run_geocoding(), name="manual-geocoding")
    return {"status": "accepted", "message": "Batch geocoding started in background"}
