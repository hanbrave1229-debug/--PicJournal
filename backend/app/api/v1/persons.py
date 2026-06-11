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

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse

from app.schemas.person import (
    FaceRunResponse,
    FaceRunStatus,
    PersonMergeRequest,
    PersonRenameRequest,
    PersonResponse,
)
from app.schemas.photo import PhotoListResponse, PhotoResponse
from app.services import face_service

router = APIRouter()


# ── Run face analysis ─────────────────────────────────────────────────────────

@router.post("/run", response_model=FaceRunResponse, summary="Run face detection + clustering")
async def run_face_analysis(
    background_tasks: BackgroundTasks,
    force: bool = Query(False, description="Re-process photos that already have face data"),
) -> FaceRunResponse:
    """
    Detect faces in all photos, cluster into persons.
    Runs synchronously (may take several minutes for large libraries).
    Use force=true to re-analyse already-processed photos.
    """
    try:
        result = await face_service.run_face_analysis(force=force)
        return result
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/status", response_model=FaceRunStatus, summary="Face analysis run status")
async def get_status() -> FaceRunStatus:
    status = await face_service.get_status()
    return FaceRunStatus(**status)


# ── Person CRUD ───────────────────────────────────────────────────────────────

@router.get("", response_model=list[PersonResponse], summary="List all persons")
async def list_persons(
    include_hidden: bool = Query(False),
) -> list[PersonResponse]:
    persons = await face_service.list_persons(include_hidden=include_hidden)
    return [PersonResponse(**p) for p in persons]


@router.get("/{person_id}", response_model=PersonResponse, summary="Get person by ID")
async def get_person(person_id: int) -> PersonResponse:
    persons = await face_service.list_persons(include_hidden=True)
    for p in persons:
        if p["id"] == person_id:
            return PersonResponse(**p)
    raise HTTPException(status_code=404, detail="Person not found")


@router.patch("/{person_id}/name", response_model=PersonResponse, summary="Rename a person")
async def rename_person(person_id: int, body: PersonRenameRequest) -> PersonResponse:
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="Name cannot be empty")
    person = await face_service.rename_person(person_id, body.name)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    # Build response dict manually (count not on ORM object)
    persons = await face_service.list_persons(include_hidden=True)
    for p in persons:
        if p["id"] == person_id:
            return PersonResponse(**p)
    raise HTTPException(status_code=404, detail="Person not found")


@router.patch("/{person_id}/hide", response_model=PersonResponse, summary="Hide / unhide a person")
async def hide_person(
    person_id: int,
    hidden: bool = Query(True),
) -> PersonResponse:
    person = await face_service.hide_person(person_id, hidden=hidden)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    persons = await face_service.list_persons(include_hidden=True)
    for p in persons:
        if p["id"] == person_id:
            return PersonResponse(**p)
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
