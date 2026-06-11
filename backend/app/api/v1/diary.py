"""
Diary API — CRUD + AI draft generation.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.diary import (
    DiaryGenerateDraftRequest,
    DiaryGenerateDraftResponse,
    DiaryMonthResponse,
    DiaryResponse,
    DiaryUpsertRequest,
)
from app.services import diary_service
from app.services.config_service import get_config

router = APIRouter()


# ── Calendar (month view) ─────────────────────────────────────────────────────

@router.get("/month", response_model=DiaryMonthResponse)
async def get_month(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: AsyncSession = Depends(get_db),
):
    """Return all diary entries for a given month for calendar rendering."""
    return await diary_service.get_month_entries(db, year, month)


# ── Single diary CRUD ─────────────────────────────────────────────────────────

@router.get("/date/{diary_date}", response_model=DiaryResponse)
async def get_by_date(
    diary_date: date,
    db: AsyncSession = Depends(get_db),
):
    diary = await diary_service.get_diary_by_date(db, diary_date)
    if not diary:
        raise HTTPException(status_code=404, detail="No diary entry for this date")
    return diary_service._to_response(diary)


@router.post("/save", response_model=DiaryResponse)
async def save_diary(
    body: DiaryUpsertRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create or update a diary entry (atomic upsert including photo associations)."""
    diary = await diary_service.upsert_diary(
        db,
        diary_date=body.diary_date,
        content=body.content,
        mood=body.mood,
        photo_ids=body.photo_ids,
    )
    return diary_service._to_response(diary)


@router.delete("/date/{diary_date}", status_code=204)
async def delete_by_date(
    diary_date: date,
    db: AsyncSession = Depends(get_db),
):
    diary = await diary_service.get_diary_by_date(db, diary_date)
    if not diary:
        raise HTTPException(status_code=404, detail="No diary entry for this date")
    await diary_service.delete_diary(db, diary)


# ── AI draft ─────────────────────────────────────────────────────────────────

@router.post("/generate-draft", response_model=DiaryGenerateDraftResponse)
async def generate_draft(
    body: DiaryGenerateDraftRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate an AI diary draft using the user's configured LLM provider.
    Collects photo EXIF + AI tags, calls LLM, returns ~150-char draft.
    """
    cfg = await get_config(db)

    if not cfg.ai_api_key:
        raise HTTPException(
            status_code=400,
            detail="AI API Key 未配置，请前往设置页完成配置",
        )

    try:
        draft = await diary_service.generate_ai_draft(
            db,
            diary_date=body.diary_date,
            photo_ids=body.photo_ids,
            mood=body.mood,
            api_key=cfg.ai_api_key,
            base_url=cfg.ai_base_url or "",
            model=cfg.ai_model or "gpt-4o-mini",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return DiaryGenerateDraftResponse(draft=draft)
