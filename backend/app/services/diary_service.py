"""
Diary service — CRUD, photo association, and AI draft generation.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Optional

import httpx
from sqlalchemy import delete, extract, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.diary import Diary, DiaryPhoto
from app.models.photo import Photo
from app.schemas.diary import (
    DiaryCalendarItem,
    DiaryMonthResponse,
    DiaryResponse,
    MoodType,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _thumbnail_url(photo: Photo) -> str | None:
    """Return a usable thumbnail URL from the photo record."""
    if photo.thumbnail_256:
        return f"/api/v1/thumbnails/{photo.id}?size=256"
    return None


def _to_response(diary: Diary) -> DiaryResponse:
    all_ids = [dp.photo_id for dp in diary.diary_photos]
    # Use explicitly stored cover_photo_id; fall back to first associated photo
    cover_pid: int | None = diary.cover_photo_id or (all_ids[0] if all_ids else None)
    cover_url: str | None = (
        f"/api/v1/thumbnails/{cover_pid}?size=256" if cover_pid else None
    )
    # Return cover photo first so frontend can restore strip display order
    if cover_pid and cover_pid in all_ids:
        photo_ids = [cover_pid] + [pid for pid in all_ids if pid != cover_pid]
    else:
        photo_ids = all_ids
    return DiaryResponse(
        id=diary.id,
        diary_date=diary.diary_date,
        content=diary.content,
        ai_draft=diary.ai_draft,
        mood=diary.mood,  # type: ignore[arg-type]
        photo_ids=photo_ids,
        photo_count=len(photo_ids),
        cover_photo_id=cover_pid,
        cover_thumbnail_url=cover_url,
        created_at=diary.created_at,
        updated_at=diary.updated_at,
    )


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def get_diary_by_date(db: AsyncSession, diary_date: date) -> Optional[Diary]:
    result = await db.execute(
        select(Diary)
        .where(Diary.diary_date == diary_date)
        .options(selectinload(Diary.diary_photos).selectinload(DiaryPhoto.photo))
    )
    return result.scalar_one_or_none()


async def get_diary(db: AsyncSession, diary_id: int) -> Optional[Diary]:
    result = await db.execute(
        select(Diary)
        .where(Diary.id == diary_id)
        .options(selectinload(Diary.diary_photos).selectinload(DiaryPhoto.photo))
    )
    return result.scalar_one_or_none()


async def upsert_diary(
    db: AsyncSession,
    diary_date: date,
    content: Optional[str],
    mood: MoodType,
    photo_ids: list[int],
    cover_photo_id: Optional[int] = None,
) -> Diary:
    """
    Atomically create or update the diary for a given date.
    Replaces the full set of photo associations.
    cover_photo_id is stored explicitly; defaults to photo_ids[0] if not given.
    """
    effective_cover = cover_photo_id or (photo_ids[0] if photo_ids else None)
    diary = await get_diary_by_date(db, diary_date)

    if diary is None:
        diary = Diary(
            diary_date=diary_date, mood=mood, content=content,
            cover_photo_id=effective_cover,
        )
        db.add(diary)
        await db.flush()  # get diary.id
    else:
        diary.content = content
        diary.mood = mood
        diary.cover_photo_id = effective_cover
        # Clear existing associations
        await db.execute(
            delete(DiaryPhoto).where(DiaryPhoto.diary_id == diary.id)
        )

    # Add new photo associations
    for pid in photo_ids:
        db.add(DiaryPhoto(diary_id=diary.id, photo_id=pid))

    await db.commit()
    await db.refresh(diary)
    # Reload with photos
    return await get_diary(db, diary.id)  # type: ignore[return-value]


async def delete_diary(db: AsyncSession, diary: Diary) -> None:
    await db.delete(diary)
    await db.commit()


# ── Month calendar data ───────────────────────────────────────────────────────

async def get_month_entries(
    db: AsyncSession, year: int, month: int
) -> DiaryMonthResponse:
    """Return all diary entries for a given month, formatted for calendar rendering."""
    result = await db.execute(
        select(Diary)
        .where(
            extract("year", Diary.diary_date) == year,
            extract("month", Diary.diary_date) == month,
        )
        .options(selectinload(Diary.diary_photos).selectinload(DiaryPhoto.photo))
        .order_by(Diary.diary_date)
    )
    diaries = result.scalars().all()

    items: list[DiaryCalendarItem] = []
    for d in diaries:
        cover_url: str | None = None
        # Use explicitly stored cover_photo_id first; fall back to first associated photo
        if d.cover_photo_id:
            cover_url = f"/api/v1/thumbnails/{d.cover_photo_id}?size=256"
        elif d.diary_photos:
            first = d.diary_photos[0].photo
            if first:
                cover_url = _thumbnail_url(first)

        summary: str | None = None
        if d.content:
            summary = d.content[:80]

        items.append(DiaryCalendarItem(
            diary_date=d.diary_date,
            mood=d.mood,  # type: ignore[arg-type]
            summary=summary,
            cover_thumbnail_url=cover_url,
            photo_count=len(d.diary_photos),
        ))

    return DiaryMonthResponse(year=year, month=month, entries=items)


# ── AI draft generation ───────────────────────────────────────────────────────

async def _resolve_active_llm(db: AsyncSession) -> tuple[str, str, str]:
    """Return (api_key, base_url, model) from the active AiModelConfig."""
    from sqlalchemy import select as sa_select
    from app.models.ai_model_config import AiModelConfig
    from app.services.crypto import decrypt as crypto_decrypt

    active = (
        await db.execute(sa_select(AiModelConfig).where(AiModelConfig.is_active.is_(True)))
    ).scalar_one_or_none()
    if not active:
        return "", "", ""
    return crypto_decrypt(active.api_key_enc or ""), (active.base_url or ""), active.model


async def _call_diary_llm(prompt: str, api_key: str, base_url: str, model: str) -> str:
    """Single-prompt chat completion. Handles reasoning models (content: null)."""
    effective_base = (base_url.rstrip("/") if base_url else "https://api.openai.com/v1")
    url = effective_base + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:  # 本地模型可无 key
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1200,
        "temperature": 0.85,
    }
    try:
        # trust_env=False：忽略 NAS 全局代理，直连本地/自建模型端点
        async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
            r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        msg = r.json()["choices"][0]["message"]
        # 推理模型可能 content 为 null，真正内容在 reasoning_content
        return (msg.get("content") or msg.get("reasoning_content") or "").strip()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"LLM API 错误 HTTP {exc.response.status_code}: {exc.response.text[:200]}")
    except Exception as exc:
        raise RuntimeError(f"AI 调用失败: {exc}")


async def polish_diary_text(db: AsyncSession, text: str) -> str:
    """Rewrite the user's rough diary text into a warmer, more polished entry."""
    api_key, base_url, model = await _resolve_active_llm(db)
    prompt = (
        "你是一位擅长日记写作的中文助手。请把下面这段用户写的日记草稿润色得更通顺、"
        "温暖自然、有画面感，保留原意和第一人称，不要编造原文没有的事实，"
        "不要使用子标题或列表，直接输出润色后的正文：\n\n"
        f"{text.strip()}"
    )
    polished = await _call_diary_llm(prompt, api_key, base_url, model)
    if not polished:
        raise RuntimeError("AI 返回为空，请重试")
    return polished


async def generate_ai_draft(
    db: AsyncSession,
    diary_date: date,
    photo_ids: list[int],
    mood: MoodType,
    # Deprecated params kept for backward compat; ignored when active config exists
    api_key: str = "",
    base_url: str = "",
    model: str = "",
) -> str:
    """
    Collect photo metadata (EXIF, AI tags, AI captions) for the specified photos,
    build a prompt, call the active AiModelConfig, and return a diary draft.
    Active config takes precedence over legacy params.
    """
    from sqlalchemy import select as sa_select
    from app.models.ai_model_config import AiModelConfig
    from app.services.crypto import decrypt as crypto_decrypt

    active_result = await db.execute(
        sa_select(AiModelConfig).where(AiModelConfig.is_active.is_(True))
    )
    active = active_result.scalar_one_or_none()
    if active:
        api_key  = crypto_decrypt(active.api_key_enc)
        base_url = active.base_url or ""
        model    = active.model
    # Gather photo context
    photo_context_lines: list[str] = []
    if photo_ids:
        result = await db.execute(
            select(Photo).where(Photo.id.in_(photo_ids))
        )
        photos = result.scalars().all()
        for p in photos:
            parts: list[str] = []
            if p.taken_at:
                parts.append(f"拍摄时间: {p.taken_at.strftime('%Y-%m-%d %H:%M')}")
            if p.camera_model:
                parts.append(f"相机: {p.camera_model}")
            if p.ai_caption:
                parts.append(f"场景: {p.ai_caption}")
            if p.ai_tags:
                try:
                    tags = json.loads(p.ai_tags)
                    parts.append(f"标签: {', '.join(tags[:6])}")
                except (json.JSONDecodeError, TypeError):
                    pass
            if parts:
                photo_context_lines.append("• " + " | ".join(parts))

    mood_labels = {
        "happy": "开心", "calm": "平静", "tired": "疲惫",
        "sad": "伤感", "energetic": "元气满满"
    }
    mood_label = mood_labels.get(mood, "平静")

    context_block = "\n".join(photo_context_lines) if photo_context_lines else "（无照片上下文）"
    prompt = (
        f"你是一位擅长日记写作的 AI 助手。\n"
        f"日期: {diary_date.strftime('%Y年%m月%d日')}\n"
        f"今日心情: {mood_label}\n"
        f"今日照片信息:\n{context_block}\n\n"
        f"请根据以上信息，以第一人称写一段约 150 字的日记草稿，"
        f"风格温暖自然，不要使用子标题或列表，直接输出正文。"
    )

    # Call LLM
    effective_base = (base_url.rstrip("/") if base_url else "https://api.openai.com/v1")
    url = effective_base + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:  # 本地模型可无 key
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1200,   # 400 会把日记从中间截断 → 文案显示不全
        "temperature": 0.85,
    }

    try:
        # trust_env=False：忽略 NAS 全局代理，直连本地/自建模型端点
        async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
            r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        draft = data["choices"][0]["message"]["content"].strip()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"LLM API 错误 HTTP {exc.response.status_code}: {exc.response.text[:200]}")
    except Exception as exc:
        raise RuntimeError(f"AI 主笔失败: {exc}")

    # Persist ai_draft on the diary row if it exists
    diary = await get_diary_by_date(db, diary_date)
    if diary:
        diary.ai_draft = draft
        await db.commit()

    return draft
