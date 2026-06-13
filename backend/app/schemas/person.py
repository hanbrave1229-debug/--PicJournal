"""
Pydantic schemas for Person / FaceCrop API responses.
"""
from __future__ import annotations

import os
from datetime import datetime

from pydantic import BaseModel, ConfigDict, computed_field


class PersonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    cover_path: str | None
    is_hidden: bool
    is_locked: bool
    photo_count: int   # injected by service layer, not from ORM directly
    created_at: datetime
    updated_at: datetime
    preview_photos: list[str] = []  # 4 newest photo thumbnail URLs

    @computed_field
    @property
    def cover_url(self) -> str | None:
        """Derive a servable URL from the local cover_path."""
        if not self.cover_path:
            return None
        filename = os.path.basename(self.cover_path)
        return f"/api/v1/persons/crops/{filename}"


class PersonListResponse(BaseModel):
    """Paginated persons list with metadata."""
    total: int
    page: int
    page_size: int
    items: list[PersonResponse]


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
