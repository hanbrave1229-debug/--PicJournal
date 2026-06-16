"""
Diary API — CRUD + AI draft generation.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.diary import Diary
from app.schemas.diary import (
    DiaryGenerateDraftRequest,
    DiaryGenerateDraftResponse,
    DiaryMonthResponse,
    DiaryPolishRequest,
    DiaryResponse,
    DiaryUpsertRequest,
)
from app.models.ai_model_config import AiModelConfig
from app.services import diary_service
from app.services.crypto import decrypt as crypto_decrypt

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
        cover_photo_id=body.cover_photo_id,
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


# ── Timeline list ────────────────────────────────────────────────────────────

@router.get("/list", summary="Diary entries as paginated timeline")
async def list_diaries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return diary entries ordered newest-first for timeline view."""
    from sqlalchemy import func as sqlfunc
    from app.models.photo import Photo

    total: int = (await db.execute(select(sqlfunc.count(Diary.id)))).scalar_one()
    rows = (
        await db.execute(
            select(Diary).order_by(desc(Diary.diary_date))
            .offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()

    items = []
    for d in rows:
        cover_url = None
        if d.cover_photo_id:
            cover_url = f"/api/v1/thumbnails/{d.cover_photo_id}?size=256"
        items.append({
            "id": d.id,
            "diary_date": d.diary_date.isoformat(),
            "mood": d.mood,
            "content": d.content,
            "cover_thumbnail_url": cover_url,
        })

    return {"total": total, "page": page, "page_size": page_size, "items": items}


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
    result = await db.execute(select(AiModelConfig).where(AiModelConfig.is_active.is_(True)))
    active_cfg = result.scalar_one_or_none()
    if not active_cfg or not crypto_decrypt(active_cfg.api_key_enc or ""):
        raise HTTPException(
            status_code=400,
            detail="AI API Key 未配置，请前往设置页选择并激活一个 AI 模型配置",
        )

    try:
        draft = await diary_service.generate_ai_draft(
            db,
            diary_date=body.diary_date,
            photo_ids=body.photo_ids,
            mood=body.mood,
            api_key="",
            base_url="",
            model="",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return DiaryGenerateDraftResponse(draft=draft)


@router.post("/polish", response_model=DiaryGenerateDraftResponse)
async def polish_diary(
    body: DiaryPolishRequest,
    db: AsyncSession = Depends(get_db),
):
    """Polish the user's own draft text into a warmer, smoother diary entry."""
    result = await db.execute(select(AiModelConfig).where(AiModelConfig.is_active.is_(True)))
    active_cfg = result.scalar_one_or_none()
    if not active_cfg or not crypto_decrypt(active_cfg.api_key_enc or ""):
        raise HTTPException(
            status_code=400,
            detail="AI API Key 未配置，请前往设置页选择并激活一个 AI 模型配置",
        )
    try:
        polished = await diary_service.polish_diary_text(db, body.text)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return DiaryGenerateDraftResponse(draft=polished)
