"""
Pydantic schemas for duplicate group responses and resolve requests.
"""
from pydantic import BaseModel, Field

from app.models.duplicate_group import DuplicateType
from app.schemas.photo import PhotoResponse


class DuplicateGroupResponse(BaseModel):
    id: int
    group_type: DuplicateType
    recommended_keep_id: int | None
    photos: list[PhotoResponse]

    model_config = {"from_attributes": True}


class ResolveRequest(BaseModel):
    """
    Request body for POST /api/v1/duplicates/resolve.
    Caller specifies which photo IDs to keep and which to soft-delete.
    """

    group_id: int
    keep_ids: list[int] = Field(description="Photo IDs to mark as kept")
    delete_ids: list[int] = Field(description="Photo IDs to soft-delete")
