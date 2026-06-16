"""
User model — application accounts for login authentication.

Middle-tier auth: a single admin is created on first deployment. The table is
multi-user ready (role column) so additional users can be added later without
schema changes.
"""
import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    # bcrypt hash of the password (never store plaintext)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)

    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.USER, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
