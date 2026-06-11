"""
Schemas for application config (AI provider settings).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class AIConfigUpdate(BaseModel):
    """Partial update payload — all fields optional."""
    ai_provider:   str | None = None   # "openai"|"anthropic"|"qianwen"|"custom"|""
    ai_api_key:    str | None = None   # write-only; plain sk-...
    ai_model:      str | None = None
    ai_base_url:   str | None = None
    ai_enabled:    bool | None = None
    ai_auto_tag:   bool | None = None
    ai_batch_size: int | None = Field(None, ge=1, le=50)


class AIConfigResponse(BaseModel):
    """Read response — api_key is always masked."""
    ai_provider:   str
    ai_api_key_masked: str    # e.g. "sk-...Ab1c"
    ai_model:      str
    ai_base_url:   str | None
    ai_enabled:    bool
    ai_auto_tag:   bool
    ai_batch_size: int

    model_config = {"from_attributes": True}


class ConnectionTestRequest(BaseModel):
    """Test connection with the given (possibly unsaved) credentials."""
    provider:  str
    api_key:   str
    model:     str
    base_url:  str | None = None


class ConnectionTestResponse(BaseModel):
    ok:      bool
    message: str
    latency_ms: int | None = None
