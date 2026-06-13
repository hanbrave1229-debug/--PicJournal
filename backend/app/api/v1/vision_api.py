"""
vision_api.py — On-demand Qwen2.5-VL analysis endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.photo import Photo
from app.services.vision_llm import (
    caption_photo,
    tag_photo,
    ocr_photo,
    recognize_landmark,
    write_journal_entry,
)

router = APIRouter()


async def _get_photo_path(photo_id: int, db: AsyncSession) -> str:
    photo = await db.get(Photo, photo_id)
    if not photo:
        raise HTTPException(404, "Photo not found")
    return photo.file_path


# ── Caption ───────────────────────────────────────────────────────────────────

@router.post("/caption/{photo_id}")
async def gen_caption(photo_id: int, db: AsyncSession = Depends(get_db)):
    path = await _get_photo_path(photo_id, db)
    text = await caption_photo(path, db)
    if not text:
        raise HTTPException(503, "视觉模型不可用，请检查设置页 AI 配置")
    return {"caption": text}


@router.post("/tags/{photo_id}")
async def gen_tags(photo_id: int, db: AsyncSession = Depends(get_db)):
    path = await _get_photo_path(photo_id, db)
    tags = await tag_photo(path, db)
    return {"tags": tags}


@router.post("/ocr/{photo_id}")
async def gen_ocr(photo_id: int, db: AsyncSession = Depends(get_db)):
    path = await _get_photo_path(photo_id, db)
    text = await ocr_photo(path, db)
    return {"text": text}


@router.post("/landmark/{photo_id}")
async def gen_landmark(photo_id: int, db: AsyncSession = Depends(get_db)):
    path = await _get_photo_path(photo_id, db)
    result = await recognize_landmark(path, db)
    return {"landmark": result}


class JournalRequest(BaseModel):
    date_str: str

@router.post("/journal/{photo_id}")
async def gen_journal(photo_id: int, body: JournalRequest, db: AsyncSession = Depends(get_db)):
    path = await _get_photo_path(photo_id, db)
    text = await write_journal_entry(path, body.date_str, db)
    if not text:
        raise HTTPException(503, "视觉模型不可用，请检查设置页 AI 配置")
    return {"entry": text}


@router.get("/progress")
async def get_vision_progress(db: AsyncSession = Depends(get_db)):
    """返回视觉分析整体进度，用于前端显示断点续跑状态。"""
    total_result = await db.execute(
        select(func.count()).select_from(Photo).where(Photo.is_deleted.is_(False))
    )
    done_result = await db.execute(
        select(func.count()).select_from(Photo).where(
            Photo.is_deleted.is_(False),
            Photo.vision_analyzed_at.is_not(None),
        )
    )
    total = total_result.scalar_one()
    done  = done_result.scalar_one()
    return {
        "total":     total,
        "done":      done,
        "pending":   total - done,
        "percent":   round(done / total * 100, 1) if total else 0,
    }


@router.get("/pending-ids")
async def get_pending_ids(
    limit: int = 500,
    db: AsyncSession = Depends(get_db),
):
    """返回尚未做视觉分析的照片 ID 列表，配合 batch 接口实现断点续跑。"""
    result = await db.execute(
        select(Photo.id)
        .where(Photo.is_deleted.is_(False), Photo.vision_analyzed_at.is_(None))
        .order_by(Photo.taken_at.asc())
        .limit(limit)
    )
    return {"ids": [row[0] for row in result.all()]}


class BatchTagRequest(BaseModel):
    photo_ids: list[int]
    concurrency: int = 2    # match LM Studio / Ollama concurrent slots
    force: bool = False     # True = re-analyze even if already done


@router.post("/tags/batch")
async def gen_tags_batch(body: BatchTagRequest, db: AsyncSession = Depends(get_db)):
    """
    Batch vision analysis with checkpoint resume.

    Each photo is marked with `vision_analyzed_at` after success.
    Re-running skips already-analyzed photos unless `force=True`.
    If the model goes offline mid-run, restart the same request to continue.
    """
    import asyncio
    import json
    from datetime import datetime, timezone

    sem = asyncio.Semaphore(max(1, body.concurrency))

    async def _one(pid: int) -> dict:
        async with sem:
            photo = await db.get(Photo, pid)
            if not photo:
                return {"photo_id": pid, "tags": [], "ok": False, "error": "not found"}

            # Skip if already analyzed and not forced
            if photo.vision_analyzed_at and not body.force:
                existing = json.loads(photo.ai_tags) if photo.ai_tags else []
                return {"photo_id": pid, "tags": existing, "ok": True, "skipped": True}

            try:
                tags = await tag_photo(photo.file_path, db)

                # Persist result + checkpoint
                photo.ai_tags = json.dumps(tags, ensure_ascii=False)
                photo.vision_analyzed_at = datetime.now(timezone.utc)
                await db.commit()

                return {"photo_id": pid, "tags": tags, "ok": True, "skipped": False}
            except Exception as e:
                await db.rollback()
                return {"photo_id": pid, "tags": [], "ok": False, "error": str(e)}

    results = list(await asyncio.gather(*[_one(pid) for pid in body.photo_ids]))

    total    = len(results)
    skipped  = sum(1 for r in results if r.get("skipped"))
    failed   = sum(1 for r in results if not r["ok"])
    processed = total - skipped - failed

    return {
        "total": total,
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
        "results": results,
    }
