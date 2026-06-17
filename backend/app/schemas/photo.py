"""
Pydantic schemas for Photo responses.
"""
from __future__ import annotations

import json
from datetime import datetime

from pydantic import BaseModel, Field


class ExifInfo(BaseModel):
    taken_at: datetime | None
    camera_make: str | None
    camera_model: str | None
    aperture: str | None
    shutter_speed: str | None
    iso: int | None
    gps_lat: float | None
    gps_lon: float | None


class PhotoScores(BaseModel):
    sharpness_score: float | None = Field(description="Laplacian variance; higher = sharper")
    exposure_score: float | None = Field(description="0.0 (dark) – 1.0 (bright)")


class PhotoResponse(BaseModel):
    id: int
    file_path: str
    file_name: str
    file_ext: str
    file_size: int
    width: int | None
    height: int | None
    md5_hash: str | None
    phash: str | None
    thumbnail_256: str | None
    thumbnail_1080: str | None
    is_deleted: bool
    duplicate_group_id: int | None
    exif: ExifInfo
    scores: PhotoScores
    # AI-generated fields (None until AI tagging has run)
    ai_caption: str | None = None
    ai_tags: list[str] = Field(default_factory=list)
    # ThumbHash progressive placeholder
    thumbhash: str | None = None
    # Offline reverse geocoding
    country: str | None = None
    province: str | None = None
    city: str | None = None
    # Archive dual-track
    is_archived: bool = False
    # Media type: "photo" | "video"
    media_type: str = "photo"
    duration: float | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, photo: object) -> "PhotoResponse":
        from app.models.photo import Photo as PhotoModel

        p: PhotoModel = photo  # type: ignore[assignment]
        return cls(
            id=p.id,
            file_path=p.file_path,
            file_name=p.file_name,
            file_ext=p.file_ext,
            file_size=p.file_size,
            width=p.width,
            height=p.height,
            md5_hash=p.md5_hash,
            phash=p.phash,
            thumbnail_256=p.thumbnail_256,
            thumbnail_1080=p.thumbnail_1080,
            is_deleted=p.is_deleted,
            duplicate_group_id=p.duplicate_group_id,
            exif=ExifInfo(
                taken_at=p.taken_at,
                camera_make=p.camera_make,
                camera_model=p.camera_model,
                aperture=p.aperture,
                shutter_speed=p.shutter_speed,
                iso=p.iso,
                gps_lat=p.gps_lat,
                gps_lon=p.gps_lon,
            ),
            scores=PhotoScores(
                sharpness_score=p.sharpness_score,
                exposure_score=p.exposure_score,
            ),
            ai_caption=p.ai_caption,
            ai_tags=json.loads(p.ai_tags) if p.ai_tags else [],
            thumbhash=p.thumbhash,
            country=p.country,
            province=p.province,
            city=p.city,
            is_archived=p.is_archived,
            media_type=getattr(p, "media_type", "photo") or "photo",
            duration=getattr(p, "duration", None),
            created_at=p.created_at,
            updated_at=p.updated_at,
        )


class PhotoListResponse(BaseModel):
    """Paginated photo list for the virtual gallery."""

    total: int
    page: int
    page_size: int
    items: list[PhotoResponse]
