"""
Geocoding API — manually trigger offline reverse geocoding.

POST /geocoding/run        batch-geocode all un-geocoded GPS photos
POST /geocoding/{photo_id} geocode a single photo
GET  /geocoding/status     DB availability + pending count
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
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


class CityItem(BaseModel):
    country: str | None
    province: str | None
    city: str
    photo_count: int
    cover_thumbnail: str | None


@router.get("/cities", response_model=list[CityItem])
async def list_cities(
    country: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[CityItem]:
    """
    Return all cities that have at least one geocoded photo,
    ordered by photo count descending.
    Optionally filter by country.
    """
    # Aggregate city + cover thumbnail (first photo per city by taken_at desc)
    city_q = (
        select(
            Photo.country,
            Photo.province,
            Photo.city,
            func.count(Photo.id).label("photo_count"),
        )
        .where(
            Photo.is_deleted.is_(False),
            Photo.is_archived.is_(False),
            Photo.city.is_not(None),
        )
        .group_by(Photo.country, Photo.province, Photo.city)
        .order_by(func.count(Photo.id).desc())
    )
    if country:
        city_q = city_q.where(Photo.country == country)

    rows = (await db.execute(city_q)).fetchall()

    items: list[CityItem] = []
    for row in rows:
        # Fetch cover: first non-deleted photo with a thumbnail in this city
        cover_stmt = (
            select(Photo.id)
            .where(
                Photo.is_deleted.is_(False),
                Photo.city == row.city,
                Photo.thumbnail_256.is_not(None),
            )
            .order_by(Photo.taken_at.desc())
            .limit(1)
        )
        cover_pid = (await db.execute(cover_stmt)).scalar_one_or_none()
        items.append(CityItem(
            country=row.country,
            province=row.province,
            city=row.city,
            photo_count=row.photo_count,
            cover_thumbnail=f"/api/v1/thumbnails/{cover_pid}?size=256" if cover_pid else None,
        ))

    return items


@router.get("/photos", response_model=list[dict])
async def photos_by_city(
    city: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(60, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return photos belonging to a specific city, newest first."""
    stmt = (
        select(Photo)
        .where(
            Photo.is_deleted.is_(False),
            Photo.is_archived.is_(False),
            Photo.city == city,
        )
        .order_by(Photo.taken_at.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    photos = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": p.id,
            "thumbnail_url": f"/api/v1/thumbnails/{p.id}?size=256",
            "taken_at": p.taken_at.isoformat() if p.taken_at else None,
            "city": p.city,
            "province": p.province,
            "country": p.country,
            "ai_caption": p.ai_caption,
        }
        for p in photos
    ]


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


@router.post("/run", status_code=202)
async def run_geocoding_batch() -> dict:
    """
    Fire-and-forget batch geocoding for all un-geocoded GPS photos.
    Returns immediately; geocoding runs in the background.
    """
    from app.services.scan_service import _run_geocoding

    asyncio.create_task(_run_geocoding(), name="manual-geocoding")
    return {"status": "accepted", "message": "Batch geocoding started in background"}


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
