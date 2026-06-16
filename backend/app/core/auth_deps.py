"""
auth_deps.py — FastAPI dependencies for extracting and validating the current
user from a JWT, supplied either via the `Authorization: Bearer` header (used by
the SPA's axios client) or an `access_token` cookie (used by <img>/<video> tags
that cannot set custom headers).
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.user import User, UserRole
from app.services import auth_service

COOKIE_NAME = "access_token"


def extract_token(request: Request) -> str | None:
    """Pull the JWT from the Authorization header, falling back to the cookie."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return request.cookies.get(COOKIE_NAME)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    token = extract_token(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")

    payload = auth_service.decode_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已过期，请重新登录")

    user = await auth_service.get_user_by_id(db, int(payload.get("sub", 0)))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不存在或已禁用")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user
