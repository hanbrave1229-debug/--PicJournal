"""
Diary models — daily photo diary and associated photo links.
"""
from datetime import date, datetime

from sqlalchemy import (
    Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Diary(Base):
    __tablename__ = "diaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    diary_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    """One diary entry per calendar day (UNIQUE constraint)."""

    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    """User-written or AI-edited diary text."""

    ai_draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Raw AI-generated draft (preserved separately from edited content)."""

    mood: Mapped[str] = mapped_column(String(16), nullable=False, default="calm")
    """One of: happy, calm, tired, sad, energetic."""

    # Multi-user isolation placeholder
    owner_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    diary_photos: Mapped[list["DiaryPhoto"]] = relationship(
        "DiaryPhoto", back_populates="diary", cascade="all, delete-orphan"
    )

    @property
    def photo_count(self) -> int:
        return len(self.diary_photos)

    def __repr__(self) -> str:
        return f"<Diary id={self.id} date={self.diary_date} mood={self.mood!r}>"


class DiaryPhoto(Base):
    """Many-to-many join table between diaries and photos."""
    __tablename__ = "diary_photos"

    diary_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("diaries.id", ondelete="CASCADE"), primary_key=True
    )
    photo_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("photos.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    diary: Mapped[Diary] = relationship("Diary", back_populates="diary_photos")
    photo: Mapped["Photo"] = relationship(  # type: ignore[name-defined]
        "Photo", back_populates="diary_photos"
    )
