"""
Persons API — people detection, listing, renaming, and photo lookup.

Endpoints:
  POST /persons/run          — run face analysis pipeline
  GET  /persons/status       — check if analysis is running
  GET  /persons              — list all persons (with photo count)
  GET  /persons/{id}         — single person detail
  PATCH /persons/{id}/name   — rename a person
  PATCH /persons/{id}/hide   — hide / unhide a person
  POST /persons/merge        — merge two persons
  GET  /persons/{id}/photos  — paginated photos for a person
  GET  /persons/{id}/face-crops/{crop_id} — serve a face crop image
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.schemas.person import (
    FaceRunResponse,
    FaceRunStatus,
    PersonListResponse,
    PersonMergeRequest,
    PersonRenameRequest,
    PersonResponse,
)
from app.schemas.photo import PhotoListResponse, PhotoResponse
from app.services import face_service

router = APIRouter()


# ── Run face analysis ─────────────────────────────────────────────────────────

@router.post("/run", summary="Kick off face detection in background — returns 202 immediately")
async def run_face_analysis(
    force: bool = Query(False, description="Re-process photos that already have face data"),
) -> dict:
    """
    Start face detection + clustering as a background asyncio task and return at once.
    Poll GET /persons/status to track progress. Safe to navigate away.
    """
    try:
        face_service.start_face_analysis(force=force)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "started", "message": "人脸识别已在后台启动，通过 /persons/status 查询进度"}


@router.get("/status", response_model=FaceRunStatus, summary="Face analysis run status")
async def get_status() -> FaceRunStatus:
    status = await face_service.get_status()
    return FaceRunStatus(**status)


# ── Person CRUD ───────────────────────────────────────────────────────────────

@router.post("/reset", summary="Delete ALL face recognition data — crops and persons")
async def reset_face_data() -> dict:
    """
    Hard reset: deletes every FaceCrop and Person row.
    Photos are NOT touched. After this, run POST /persons/run to re-detect from scratch.
    Useful when the person list has ballooned due to incremental clustering bugs.
    """
    if face_service._is_running:
        raise HTTPException(status_code=409, detail="Face analysis is currently running — wait for it to finish before resetting")
    return await face_service.reset_face_data()


@router.post("/prune", summary="Delete persons with fewer than min_photos photos")
async def prune_persons(min_photos: int = Query(2, ge=1, le=20)) -> dict:
    """
    Remove Person rows whose photo count is below min_photos (default 2).
    Cleans up the long tail of 1-photo false positives after re-clustering.
    Locked persons are never pruned.
    """
    if face_service._is_running:
        raise HTTPException(status_code=409, detail="Face analysis is currently running")
    return await face_service.prune_small_persons(min_photos)


@router.post("/rebuild-covers", summary="Backfill cover_path for persons missing one")
async def rebuild_covers() -> dict:
    """
    One-time fix: scan all Person rows with cover_path=NULL and populate from
    their first FaceCrop that has a saved crop image file.
    Safe to call repeatedly (idempotent).
    """
    return await face_service.rebuild_covers()


@router.get("", response_model=PersonListResponse, summary="List persons with pagination and preview photos")
async def list_persons(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=200, description="Items per page"),
    include_hidden: bool = Query(False),
) -> PersonListResponse:
    data = await face_service.list_persons(
        include_hidden=include_hidden,
        page=page,
        page_size=page_size,
    )
    return PersonListResponse(
        total=data["total"],
        page=data["page"],
        page_size=data["page_size"],
        items=[PersonResponse(**p) for p in data["items"]],
    )


@router.get("/{person_id}", response_model=PersonResponse, summary="Get person by ID")
async def get_person(person_id: int) -> PersonResponse:
    p = await face_service.get_person_by_id(person_id)
    if not p:
        raise HTTPException(status_code=404, detail="Person not found")
    return PersonResponse(**p)


@router.patch("/{person_id}/name", response_model=PersonResponse, summary="Rename a person")
async def rename_person(person_id: int, body: PersonRenameRequest) -> PersonResponse:
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="Name cannot be empty")
    person = await face_service.rename_person(person_id, body.name)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    p = await face_service.get_person_by_id(person_id)
    return PersonResponse(**p)  # type: ignore[arg-type]


@router.patch("/{person_id}/hide", response_model=PersonResponse, summary="Hide / unhide a person")
async def hide_person(
    person_id: int,
    hidden: bool = Query(True),
) -> PersonResponse:
    person = await face_service.hide_person(person_id, hidden=hidden)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    p = await face_service.get_person_by_id(person_id)
    return PersonResponse(**p)  # type: ignore[arg-type]


@router.patch("/{person_id}/lock", response_model=PersonResponse, summary="Lock / unlock a person")
async def lock_person(
    person_id: int,
    locked: bool = Query(True),
) -> PersonResponse:
    person = await face_service.lock_person(person_id, locked=locked)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    p = await face_service.get_person_by_id(person_id)
    return PersonResponse(**p)  # type: ignore[arg-type]


@router.delete("/{person_id}", status_code=204, summary="Delete a person (keep photos)")
async def delete_person(person_id: int) -> None:
    """
    Delete the person and all their face recognition data.
    The underlying photos are NOT deleted.
    Returns 423 if the person is locked.
    """
    try:
        found = await face_service.delete_person(person_id)
    except ValueError as exc:
        raise HTTPException(status_code=423, detail=str(exc)) from exc
    if not found:
        raise HTTPException(status_code=404, detail="Person not found")


@router.post("/merge", response_model=dict, summary="Merge two persons")
async def merge_persons(body: PersonMergeRequest) -> dict:
    ok = await face_service.merge_persons(body.source_id, body.target_id)
    if not ok:
        raise HTTPException(status_code=404, detail="One or both persons not found")
    return {"ok": True, "message": f"Merged person {body.source_id} into {body.target_id}"}


# ── Person photos ─────────────────────────────────────────────────────────────

@router.get("/{person_id}/photos", response_model=PhotoListResponse, summary="Photos containing a person")
async def get_person_photos(
    person_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(80, ge=1, le=200),
) -> PhotoListResponse:
    data = await face_service.get_person_photos(person_id, page=page, page_size=page_size)
    return PhotoListResponse(
        total=data["total"],
        page=data["page"],
        page_size=data["page_size"],
        items=[PhotoResponse.model_validate(p, from_attributes=True) for p in data["items"]],
    )


# ── Serve face crop images ────────────────────────────────────────────────────

@router.get("/crops/{filename}", response_class=FileResponse, summary="Serve face crop image")
async def serve_face_crop(filename: str) -> FileResponse:
    from pathlib import Path
    from app.config import get_settings
    settings = get_settings()
    path = Path(settings.thumbnails_dir) / "faces" / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Face crop not found")
    return FileResponse(str(path), media_type="image/jpeg")
