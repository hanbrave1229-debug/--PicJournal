"""
Pydantic schemas for Person / FaceCrop API responses.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PersonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    cover_path: str | None
    is_hidden: bool
    photo_count: int   # injected by service layer, not from ORM directly
    created_at: datetime
    updated_at: datetime


class PersonRenameRequest(BaseModel):
    name: str


class PersonMergeRequest(BaseModel):
    """Merge source_id into target_id — all faces reassigned to target, source deleted."""
    source_id: int
    target_id: int


class FaceRunResponse(BaseModel):
    """Summary returned after running the face analysis pipeline."""
    photos_processed: int
    faces_detected: int
    persons_created: int
    persons_updated: int
    message: str


class FaceRunStatus(BaseModel):
    """Lightweight status for polling."""
    running: bool
    last_run_result: FaceRunResponse | None = None
