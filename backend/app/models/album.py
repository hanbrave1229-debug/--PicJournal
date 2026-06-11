"""
Album models — virtual albums and their photo associations.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Album(Base):
    __tablename__ = "albums"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Cover photo — SET NULL on photo deletion
    cover_photo_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("photos.id", ondelete="SET NULL"), nullable=True
    )

    # Smart album support (Phase 2)
    is_smart: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    smart_rules: Mapped[str | None] = mapped_column(Text, nullable=True)
    """JSON string defining filter conditions for smart albums."""

    # Multi-user isolation placeholder (Phase 2)
    owner_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    cover_photo: Mapped["Photo | None"] = relationship(  # type: ignore[name-defined]
        "Photo", foreign_keys=[cover_photo_id]
    )
    album_photos: Mapped[list["AlbumPhoto"]] = relationship(
        "AlbumPhoto", back_populates="album", cascade="all, delete-orphan"
    )

    @property
    def photo_count(self) -> int:
        return len(self.album_photos)

    def __repr__(self) -> str:
        return f"<Album id={self.id} title={self.title!r}>"


class AlbumPhoto(Base):
    """Many-to-many join table between albums and photos."""
    __tablename__ = "album_photos"

    album_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("albums.id", ondelete="CASCADE"), primary_key=True
    )
    photo_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("photos.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    album: Mapped[Album] = relationship("Album", back_populates="album_photos")
    photo: Mapped["Photo"] = relationship(  # type: ignore[name-defined]
        "Photo", back_populates="album_photos"
    )
