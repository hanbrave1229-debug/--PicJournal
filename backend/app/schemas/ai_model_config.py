"""
Schemas for AiModelConfig.
api_key is NEVER returned in plaintext — only a masked display string.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AiModelConfigCreate(BaseModel):
    name: str = Field(..., max_length=64)
    provider: str = Field("custom", max_length=32)
    api_key: str = Field("", description="Plaintext key — encrypted before storage")
    base_url: str | None = None
    model: str = Field(..., max_length=128)


class AiModelConfigUpdate(BaseModel):
    name: str | None = Field(None, max_length=64)
    provider: str | None = Field(None, max_length=32)
    # Empty string = keep existing key unchanged
    api_key: str | None = Field(None, description="Omit or empty to keep existing key")
    base_url: str | None = None
    model: str | None = Field(None, max_length=128)


class AiModelConfigResponse(BaseModel):
    id: int
    name: str
    provider: str
    # Masked display string, e.g. "sk-pr****...****oWx3"
    api_key_masked: str
    base_url: str | None
    model: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
