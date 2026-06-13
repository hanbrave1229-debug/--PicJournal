"""
vision_api.py — On-demand Qwen2.5-VL analysis endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
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


class BatchTagRequest(BaseModel):
    photo_ids: list[int]
    concurrency: int = 2   # match OLLAMA_NUM_PARALLEL

@router.post("/tags/batch")
async def gen_tags_batch(body: BatchTagRequest, db: AsyncSession = Depends(get_db)):
    import asyncio
    sem = asyncio.Semaphore(max(1, body.concurrency))

    async def _one(pid: int) -> dict:
        async with sem:
            try:
                path = await _get_photo_path(pid, db)
                tags = await tag_photo(path, db)
                return {"photo_id": pid, "tags": tags, "ok": True}
            except Exception as e:
                return {"photo_id": pid, "tags": [], "ok": False, "error": str(e)}

    results = await asyncio.gather(*[_one(pid) for pid in body.photo_ids])
    return {"results": list(results)}
