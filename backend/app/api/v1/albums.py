"""
Albums API — CRUD + photo association endpoints.
"""
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.album import (
    AlbumAddPhotosRequest,
    AlbumCreateRequest,
    AlbumListResponse,
    AlbumRemovePhotosRequest,
    AlbumResponse,
    AlbumUpdateRequest,
)
from app.schemas.photo import PhotoListResponse, PhotoResponse
from app.services import album_service

router = APIRouter()


# ── Album CRUD ────────────────────────────────────────────────────────────────

@router.post("", response_model=AlbumResponse, status_code=201)
async def create_album(
    body: AlbumCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    smart_rules_str = (
        json.dumps(body.smart_rules.model_dump(exclude_none=True))
        if body.smart_rules
        else None
    )
    album = await album_service.create_album(
        db,
        title=body.title,
        description=body.description,
        is_smart=body.is_smart,
        smart_rules=smart_rules_str,
    )
    return _to_response(album)


@router.get("", response_model=AlbumListResponse)
async def list_albums(db: AsyncSession = Depends(get_db)):
    albums = await album_service.list_albums(db)
    return AlbumListResponse(
        items=[_to_response(a) for a in albums],
        total=len(albums),
    )


@router.get("/smart", response_model=AlbumListResponse)
async def list_smart_albums(db: AsyncSession = Depends(get_db)):
    """List all smart (conditional) albums."""
    albums = await album_service.list_smart_albums(db)
    return AlbumListResponse(
        items=[_to_response(a) for a in albums],
        total=len(albums),
    )


@router.post("/{album_id}/evaluate", response_model=PhotoListResponse)
async def evaluate_smart_album(
    album_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(60, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Dynamically evaluate a smart album's rules and return matching photos."""
    album = await album_service.get_album(db, album_id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")
    if not album.is_smart:
        raise HTTPException(status_code=400, detail="Album is not a smart album")
    photos, total = await album_service.resolve_smart_album_photos(
        album.smart_rules or "{}", db, page, page_size
    )
    return PhotoListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[PhotoResponse.from_orm(p) for p in photos],
    )


@router.get("/{album_id}", response_model=AlbumResponse)
async def get_album(album_id: int, db: AsyncSession = Depends(get_db)):
    album = await album_service.get_album(db, album_id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")
    return _to_response(album)


@router.patch("/{album_id}", response_model=AlbumResponse)
async def update_album(
    album_id: int,
    body: AlbumUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    album = await album_service.get_album(db, album_id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")
    album = await album_service.update_album(
        db, album,
        title=body.title,
        description=body.description,
        cover_photo_id=body.cover_photo_id,
    )
    return _to_response(album)


@router.delete("/{album_id}", status_code=204)
async def delete_album(album_id: int, db: AsyncSession = Depends(get_db)):
    album = await album_service.get_album(db, album_id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")
    await album_service.delete_album(db, album)


# ── Album photos ──────────────────────────────────────────────────────────────

@router.get("/{album_id}/photos")
async def list_album_photos(
    album_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(60, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    album = await album_service.get_album(db, album_id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")
    photos, total = await album_service.list_album_photos(db, album_id, page, page_size)
    return {
        "items": [PhotoResponse.model_validate(p) for p in photos],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/{album_id}/photos", status_code=200)
async def add_photos(
    album_id: int,
    body: AlbumAddPhotosRequest,
    db: AsyncSession = Depends(get_db),
):
    album = await album_service.get_album(db, album_id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")
    added = await album_service.add_photos_to_album(db, album_id, body.photo_ids)
    return {"added": added}


@router.delete("/{album_id}/photos", status_code=200)
async def remove_photos(
    album_id: int,
    body: AlbumRemovePhotosRequest,
    db: AsyncSession = Depends(get_db),
):
    album = await album_service.get_album(db, album_id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")
    await album_service.remove_photos_from_album(db, album_id, body.photo_ids)
    return {"removed": len(body.photo_ids)}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_response(album) -> AlbumResponse:
    return AlbumResponse(
        id=album.id,
        title=album.title,
        description=album.description,
        cover_photo_id=album.cover_photo_id,
        is_smart=album.is_smart,
        smart_rules=album.smart_rules,
        photo_count=len(album.album_photos) if hasattr(album, "album_photos") else 0,
        created_at=album.created_at,
        updated_at=album.updated_at,
    )
