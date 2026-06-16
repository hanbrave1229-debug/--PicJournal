"""
auth_service.py — authentication helpers: password hashing (bcrypt),
JWT issuing/verification, and user lookup.

JWT signing secret is persisted at /app/data/secrets/jwt.key (same volume as
the Fernet key) so tokens survive container restarts. If the volume is not
persisted, the secret regenerates and all existing tokens become invalid
(users must log in again) — but no data is lost.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import bcrypt
import jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

_JWT_KEY_PATH = Path("/app/data/secrets/jwt.key")
_JWT_ALGORITHM = "HS256"
# Token lifetime — long enough to be convenient, short enough to limit exposure
# if a token leaks. 30 days suits a personal NAS app.
_TOKEN_TTL = timedelta(days=30)


@lru_cache(maxsize=1)
def _get_jwt_secret() -> str:
    """Load or generate the JWT signing secret (cached for process lifetime)."""
    if _JWT_KEY_PATH.exists():
        return _JWT_KEY_PATH.read_text().strip()
    secret = secrets.token_urlsafe(48)
    _JWT_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _JWT_KEY_PATH.write_text(secret)
    logger.info("auth: generated new JWT secret at %s", _JWT_KEY_PATH)
    return secret


# ── Password hashing ──────────────────────────────────────────────────────────

def hash_password(plaintext: str) -> str:
    return bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt()).decode()


def verify_password(plaintext: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plaintext.encode(), password_hash.encode())
    except (ValueError, TypeError):
        return False


# ── JWT ─────────────────────────────────────────────────────────────────────

def create_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role.value,
        "iat": now,
        "exp": now + _TOKEN_TTL,
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=_JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Return the decoded payload, or None if invalid/expired."""
    try:
        return jwt.decode(token, _get_jwt_secret(), algorithms=[_JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


# ── User helpers ──────────────────────────────────────────────────────────────

async def count_users(db: AsyncSession) -> int:
    return (await db.execute(select(func.count(User.id)))).scalar_one()

async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    return (
        await db.execute(select(User).where(User.username == username))
    ).scalar_one_or_none()

async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)

async def create_user(
    db: AsyncSession, username: str, password: str, role: UserRole = UserRole.USER
) -> User:
    user = User(
        username=username,
        password_hash=hash_password(password),
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
