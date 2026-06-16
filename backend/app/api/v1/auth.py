"""
Auth API — login, first-deploy setup, current user, password change.

Endpoints:
  GET  /auth/setup-status     → whether an admin has been created yet
  POST /auth/setup            → create the first admin (only when no users exist)
  POST /auth/login            → verify credentials, return token + set cookie
  POST /auth/logout           → clear the auth cookie
  GET  /auth/me               → current user info
  POST /auth/change-password  → change own password
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_deps import COOKIE_NAME, get_current_user
from app.db.database import get_db
from app.models.user import User, UserRole
from app.services import auth_service

router = APIRouter()

# Cookie lifetime in seconds — mirrors the JWT TTL (30 days).
_COOKIE_MAX_AGE = 30 * 24 * 3600


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        # secure=False so it works over plain HTTP on a LAN. Behind an HTTPS
        # reverse proxy the browser still sends it; flip to True if HTTPS-only.
        secure=False,
    )


# ── Schemas ───────────────────────────────────────────────────────────────────

class SetupStatusResponse(BaseModel):
    initialized: bool

class SetupRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)

class LoginRequest(BaseModel):
    username: str
    password: str

class UserInfo(BaseModel):
    id: int
    username: str
    role: str

class LoginResponse(BaseModel):
    token: str
    user: UserInfo

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/setup-status", response_model=SetupStatusResponse, summary="是否已初始化管理员")
async def setup_status(db: AsyncSession = Depends(get_db)) -> SetupStatusResponse:
    return SetupStatusResponse(initialized=await auth_service.count_users(db) > 0)


@router.post("/setup", response_model=LoginResponse, summary="首次部署创建管理员")
async def setup(
    body: SetupRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> LoginResponse:
    if await auth_service.count_users(db) > 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="系统已初始化，无法重复创建管理员")
    user = await auth_service.create_user(db, body.username, body.password, role=UserRole.ADMIN)
    token = auth_service.create_token(user)
    _set_auth_cookie(response, token)
    return LoginResponse(token=token, user=UserInfo(id=user.id, username=user.username, role=user.role.value))


@router.post("/login", response_model=LoginResponse, summary="登录")
async def login(
    body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> LoginResponse:
    user = await auth_service.get_user_by_username(db, body.username)
    if user is None or not auth_service.verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")
    token = auth_service.create_token(user)
    _set_auth_cookie(response, token)
    return LoginResponse(token=token, user=UserInfo(id=user.id, username=user.username, role=user.role.value))


@router.post("/logout", summary="登出")
async def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


@router.get("/me", response_model=UserInfo, summary="当前用户")
async def me(user: User = Depends(get_current_user)) -> UserInfo:
    return UserInfo(id=user.id, username=user.username, role=user.role.value)


@router.post("/change-password", summary="修改自己的密码")
async def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not auth_service.verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误")
    user.password_hash = auth_service.hash_password(body.new_password)
    await db.commit()
    return {"ok": True}
