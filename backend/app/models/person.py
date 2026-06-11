"""
Person and FaceCrop models for face recognition / people grouping.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Person(Base):
    """
    Represents a unique individual identified across the photo library.
    Created by DBSCAN clustering of face embeddings.
    """
    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Human-readable name; default is "人物 N" until user renames
    name: Mapped[str] = mapped_column(String(256), nullable=False, default="未命名")

    # Path to the representative face crop image (used as avatar)
    cover_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # Whether this person was hidden/merged by the user
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    face_crops: Mapped[list["FaceCrop"]] = relationship(
        "FaceCrop", back_populates="person", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Person id={self.id} name={self.name!r}>"


class FaceCrop(Base):
    """
    One detected face within a photo.
    Multiple FaceCrops may be assigned to the same Person.
    """
    __tablename__ = "face_crops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Source photo ──────────────────────────────────────────────────────────
    photo_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("photos.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ── Assigned person (null = unassigned / noise) ───────────────────────────
    person_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("persons.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # ── Bounding box (pixels, top-left origin) ────────────────────────────────
    bbox_top: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_right: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_bottom: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_left: Mapped[int] = mapped_column(Integer, nullable=False)

    # ── 128-dim face embedding stored as comma-separated floats ───────────────
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Detection confidence (0.0–1.0); dlib HOG doesn't provide confidence so
    # we store 1.0 when using the HOG model.
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    # Path to cropped face JPEG (for avatar display)
    crop_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    person: Mapped["Person | None"] = relationship("Person", back_populates="face_crops")

    def __repr__(self) -> str:
        return f"<FaceCrop id={self.id} photo_id={self.photo_id} person_id={self.person_id}>"
