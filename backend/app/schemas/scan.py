"""
Pydantic schemas for scan task request / response.
"""
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.scan_task import ScanStatus


class ScanRequest(BaseModel):
    """Request body for POST /api/v1/scan/start."""

    scan_path: str = Field(
        ...,
        description="Absolute path inside the container to scan (e.g. /photos or /photos/2024)",
        examples=["/photos"],
    )


class ScanStatusResponse(BaseModel):
    """Response for scan task status queries."""

    id: int
    scan_path: str
    status: ScanStatus
    total_files: int
    processed_files: int
    progress_pct: float = Field(default=0.0, description="0.0–100.0")
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_progress(cls, task: object) -> "ScanStatusResponse":
        """Compute progress_pct from total/processed counters."""
        obj = cls.model_validate(task)
        if obj.total_files > 0:
            obj.progress_pct = round(obj.processed_files / obj.total_files * 100, 1)
        return obj
