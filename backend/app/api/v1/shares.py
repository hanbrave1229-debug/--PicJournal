"""
Shares API — public read-only share links for albums.

Auth model:
  - Management endpoints (create/list/revoke) require a logged-in user.
  - Public endpoints (`/shares/public/...`) need NO login — they validate the
    share token (and optional password) themselves. They are whitelisted in the
    auth middleware so anyone with the link can view.

Photo thumbnails are already served without auth (by id), so once the public
viewer has the photo ids it can render them directly.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.album import Album
from app.models.share import AlbumShare
from app.schemas.photo import PhotoResponse
from app.services import album_service, auth_service

router = APIRouter()


# ── Schemas ─────────────────────────────────────────────────────────────────

class CreateShareRequest(BaseModel):
    album_id: int
    password: str | None = Field(None, max_length=128)
    expires_days: int | None = Field(None, ge=1, le=3650)


class ShareInfo(BaseModel):
    token: str
    album_id: int
    album_title: str
    has_password: bool
    expires_at: datetime | None
    view_count: int
    created_at: datetime


class PublicShareMeta(BaseModel):
    album_title: str
    photo_count: int
    needs_password: bool
    cover_id: int | None


class VerifyRequest(BaseModel):
    password: str | None = None


# ── Helpers ─────────────────────────────────────────────────────────────────

def _is_expired(share: AlbumShare) -> bool:
    if share.expires_at is None:
        return False
    exp = share.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > exp


async def _get_share(db: AsyncSession, token: str) -> AlbumShare:
    share = (
        await db.execute(select(AlbumShare).where(AlbumShare.token == token))
    ).scalar_one_or_none()
    if share is None:
        raise HTTPException(status_code=404, detail="分享链接不存在")
    if _is_expired(share):
        raise HTTPException(status_code=410, detail="分享链接已过期")
    return share


# ── Management (authed) ───────────────────────────────────────────────────────

@router.post("", response_model=ShareInfo, summary="创建相册分享链接")
async def create_share(
    body: CreateShareRequest, db: AsyncSession = Depends(get_db)
) -> ShareInfo:
    album = await album_service.get_album(db, body.album_id)
    if not album:
        raise HTTPException(status_code=404, detail="相册不存在")

    expires_at = None
    if body.expires_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_days)

    share = AlbumShare(
        token=secrets.token_urlsafe(16),
        album_id=body.album_id,
        password_hash=auth_service.hash_password(body.password) if body.password else None,
        expires_at=expires_at,
    )
    db.add(share)
    await db.commit()
    await db.refresh(share)

    return ShareInfo(
        token=share.token,
        album_id=share.album_id,
        album_title=album.title,
        has_password=share.password_hash is not None,
        expires_at=share.expires_at,
        view_count=share.view_count,
        created_at=share.created_at,
    )


@router.get("/album/{album_id}", response_model=list[ShareInfo], summary="某相册的所有分享链接")
async def list_shares(album_id: int, db: AsyncSession = Depends(get_db)) -> list[ShareInfo]:
    album = await album_service.get_album(db, album_id)
    if not album:
        raise HTTPException(status_code=404, detail="相册不存在")
    rows = (
        await db.execute(
            select(AlbumShare).where(AlbumShare.album_id == album_id)
            .order_by(AlbumShare.created_at.desc())
        )
    ).scalars().all()
    return [
        ShareInfo(
            token=s.token,
            album_id=s.album_id,
            album_title=album.title,
            has_password=s.password_hash is not None,
            expires_at=s.expires_at,
            view_count=s.view_count,
            created_at=s.created_at,
        )
        for s in rows
    ]


@router.delete("/{token}", status_code=204, summary="撤销分享链接")
async def revoke_share(token: str, db: AsyncSession = Depends(get_db)) -> None:
    share = (
        await db.execute(select(AlbumShare).where(AlbumShare.token == token))
    ).scalar_one_or_none()
    if share is None:
        raise HTTPException(status_code=404, detail="分享链接不存在")
    await db.delete(share)
    await db.commit()


# ── Public (no auth — whitelisted in middleware) ──────────────────────────────

@router.get("/public/{token}", response_model=PublicShareMeta, summary="公开：分享元信息")
async def public_meta(token: str, db: AsyncSession = Depends(get_db)) -> PublicShareMeta:
    share = await _get_share(db, token)
    album = await album_service.get_album(db, share.album_id)
    if not album:
        raise HTTPException(status_code=404, detail="相册不存在")
    _, total = await album_service.list_album_photos(db, share.album_id, 1, 1)
    return PublicShareMeta(
        album_title=album.title,
        photo_count=total,
        needs_password=share.password_hash is not None,
        cover_id=album.cover_photo_id,
    )


@router.post("/public/{token}/photos", summary="公开：验证密码并返回照片")
async def public_photos(
    token: str,
    body: VerifyRequest,
    page: int = 1,
    page_size: int = 100,
    db: AsyncSession = Depends(get_db),
) -> dict:
    share = await _get_share(db, token)

    if share.password_hash is not None:
        if not body.password or not auth_service.verify_password(body.password, share.password_hash):
            raise HTTPException(status_code=401, detail="密码错误")

    page_size = min(max(page_size, 1), 200)
    photos, total = await album_service.list_album_photos(db, share.album_id, page, page_size)

    # Count a view once (first page only)
    if page == 1:
        share.view_count += 1
        await db.commit()

    return {
        "items": [PhotoResponse.from_orm(p) for p in photos],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
