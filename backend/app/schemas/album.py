"""
Pydantic schemas for Album and Trash endpoints.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Album schemas ─────────────────────────────────────────────────────────────

class SmartAlbumRules(BaseModel):
    """Rule set for a smart (conditional) album."""
    camera_model: Optional[str] = None
    quality_score_gt: Optional[float] = Field(None, ge=0, le=1000)
    date_after: Optional[str] = None   # "YYYY-MM-DD"
    date_before: Optional[str] = None  # "YYYY-MM-DD"
    country: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    tags_contain: Optional[str] = None  # AI tag substring match


class AlbumCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=64)
    description: Optional[str] = None
    is_smart: bool = False
    smart_rules: Optional[SmartAlbumRules] = None


class AlbumUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=64)
    description: Optional[str] = None
    cover_photo_id: Optional[int] = None
    smart_rules: Optional[SmartAlbumRules] = None


class AlbumResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    cover_photo_id: Optional[int]
    cover_thumbnail_url: Optional[str] = None
    is_smart: bool
    smart_rules: Optional[str] = None
    photo_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlbumListResponse(BaseModel):
    items: list[AlbumResponse]
    total: int


# ── Album photo management ────────────────────────────────────────────────────

class AlbumAddPhotosRequest(BaseModel):
    photo_ids: list[int] = Field(..., min_length=1)


class AlbumRemovePhotosRequest(BaseModel):
    photo_ids: list[int] = Field(..., min_length=1)


# ── Trash schemas ─────────────────────────────────────────────────────────────

class TrashPhotoResponse(BaseModel):
    id: int
    file_name: str
    file_path: str
    file_size: int
    thumbnail_256: Optional[str]
    deleted_at: Optional[datetime]
    taken_at: Optional[datetime]

    model_config = {"from_attributes": True}


class TrashListResponse(BaseModel):
    items: list[TrashPhotoResponse]
    total: int
