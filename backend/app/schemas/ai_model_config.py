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
    # Prefer api_key_cipher (RSA-OAEP encrypted by frontend); api_key is the legacy plaintext field
    api_key_cipher: str | None = Field(None, description="RSA-OAEP encrypted key (base64)")
    api_key: str = Field("", description="Plaintext fallback (for internal/migration use)")
    base_url: str | None = None
    model: str = Field(..., max_length=128)


class AiModelConfigUpdate(BaseModel):
    name: str | None = Field(None, max_length=64)
    provider: str | None = Field(None, max_length=32)
    # Prefer api_key_cipher; api_key is legacy plaintext
    api_key_cipher: str | None = Field(None, description="RSA-OAEP encrypted key (base64)")
    api_key: str | None = Field(None, description="Omit or empty to keep existing key (legacy)")
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
