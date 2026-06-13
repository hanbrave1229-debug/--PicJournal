"""
AiModelConfig — one row per saved AI provider configuration.
Only one row may have is_active=True at a time (enforced at service layer).
api_key is stored Fernet-encrypted.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AiModelConfig(Base):
    __tablename__ = "ai_model_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # User-defined label shown in the UI
    name: Mapped[str] = mapped_column(String(64), nullable=False)

    # Provider hint for UI icons / default base_url suggestions
    # e.g. "openai" | "anthropic" | "qianwen" | "custom"
    provider: Mapped[str] = mapped_column(String(32), default="custom", nullable=False)

    # Fernet-encrypted API key — NEVER store plaintext
    api_key_enc: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # Base URL; None = use provider default (e.g. https://api.openai.com/v1)
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Model identifier as understood by the endpoint
    model: Mapped[str] = mapped_column(String(128), nullable=False)

    # Whether this config is the one currently in use
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
