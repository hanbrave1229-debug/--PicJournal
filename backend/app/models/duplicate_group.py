"""
DuplicateGroup model — groups of photos detected as exact/similar/burst duplicates.
"""
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class DuplicateType(str, enum.Enum):
    EXACT = "exact"      # Identical MD5 hash
    SIMILAR = "similar"  # pHash hamming distance within threshold
    BURST = "burst"      # Same scene, rapid consecutive shots


class DuplicateGroup(Base):
    __tablename__ = "duplicate_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    group_type: Mapped[DuplicateType] = mapped_column(
        Enum(DuplicateType), nullable=False
    )

    # ID of the photo recommended to keep (highest resolution / score)
    recommended_keep_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Back-reference: all photos in this group
    photos: Mapped[list["Photo"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Photo", back_populates="duplicate_group", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<DuplicateGroup id={self.id} type={self.group_type}>"
