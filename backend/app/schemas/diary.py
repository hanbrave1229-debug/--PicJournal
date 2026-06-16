"""
Pydantic schemas for the Diary module.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

MoodType = Literal["happy", "calm", "tired", "sad", "energetic"]


# ── Request schemas ───────────────────────────────────────────────────────────

class DiaryUpsertRequest(BaseModel):
    """Create or update a diary entry for a given date."""
    diary_date: date
    content: str | None = None
    mood: MoodType = "calm"
    photo_ids: list[int] = Field(default_factory=list)
    cover_photo_id: int | None = None
    """Explicit cover photo — should be photo_ids[0] when set."""


class DiaryGenerateDraftRequest(BaseModel):
    """Request AI draft generation for a given date."""
    diary_date: date
    photo_ids: list[int] = Field(default_factory=list)
    mood: MoodType = "calm"


class DiaryPolishRequest(BaseModel):
    """Request AI polishing of the user's own draft text."""
    text: str = Field(min_length=10)


# ── Response schemas ──────────────────────────────────────────────────────────

class DiaryPhotoItem(BaseModel):
    """Minimal photo info embedded in a diary response."""
    id: int
    thumbnail_url: str | None = None
    file_name: str

    model_config = {"from_attributes": True}


class DiaryResponse(BaseModel):
    id: int
    diary_date: date
    content: str | None
    ai_draft: str | None
    mood: MoodType
    photo_ids: list[int]
    photo_count: int
    cover_photo_id: int | None = None
    cover_thumbnail_url: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DiaryCalendarItem(BaseModel):
    """Lightweight record for calendar grid rendering (month view)."""
    diary_date: date
    mood: MoodType
    summary: str | None
    """First 80 chars of content — used for hover preview."""
    cover_thumbnail_url: str | None
    photo_count: int


class DiaryMonthResponse(BaseModel):
    year: int
    month: int
    entries: list[DiaryCalendarItem]


class DiaryGenerateDraftResponse(BaseModel):
    draft: str
