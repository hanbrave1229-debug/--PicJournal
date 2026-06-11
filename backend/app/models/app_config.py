"""
AppConfig — single-row application settings table.
Stores AI provider config and other app-level preferences.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AppConfig(Base):
    __tablename__ = "app_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    # ── AI provider ───────────────────────────────────────────────────────────
    # "openai" | "anthropic" | "qianwen" | "custom" | ""
    ai_provider: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    # Stored as-is; mask in GET response
    ai_api_key: Mapped[str] = mapped_column(Text, default="", nullable=False)
    ai_model: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    # Used only for "custom" provider
    ai_base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ── AI behaviour ──────────────────────────────────────────────────────────
    ai_auto_tag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_batch_size: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
