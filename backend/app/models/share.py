"""
Share model — public share links for albums.

A share link grants read-only access to an album's photos without logging in.
Optionally protected by a password and/or an expiry date.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AlbumShare(Base):
    __tablename__ = "album_shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Unguessable URL token (secrets.token_urlsafe)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    album_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("albums.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # bcrypt hash; NULL = no password
    password_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # NULL = never expires
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
