"""
语义向量搜索 API
================
  POST /semantic/search       — 文本→图片 cosine similarity 搜索
  POST /semantic/embed        — 触发批量嵌入（后台任务）
  GET  /semantic/status       — 嵌入进度 + 模型可用性
  GET  /semantic/similar/{id} — 以某张照片为查询，找最相似的照片
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from app.services import clip_service
from app.schemas.photo import PhotoResponse
from app.db.database import AsyncSessionLocal
from app.models.photo import Photo
from sqlalchemy import select

logger = logging.getLogger(__name__)
router = APIRouter()

_batch_running = False


class SemanticSearchRequest(BaseModel):
    query: str
    top_k: int = 40


class SemanticSearchResult(BaseModel):
    id: int
    thumbnail_256: str | None
    taken_at: str | None
    ai_caption: str | None
    score: float


@router.get("/status", summary="CLIP 嵌入状态")
async def get_status() -> dict:
    return await clip_service.get_status()


@router.post("/embed", summary="触发批量 CLIP 嵌入（后台运行）")
async def start_embedding(
    background_tasks: BackgroundTasks,
    force: bool = Query(False, description="重新嵌入所有照片（包括已嵌入的）"),
) -> dict:
    global _batch_running
    if _batch_running:
        raise HTTPException(status_code=409, detail="嵌入任务已在运行中")

    if not await clip_service.is_available():
        raise HTTPException(
            status_code=503,
            detail="CLIP 模型不可用。首次使用需联网下载 (~340 MB)，请确认容器可访问 HuggingFace。",
        )

    background_tasks.add_task(_run_batch, force)
    return {"status": "started", "message": "CLIP 批量嵌入已在后台启动"}


async def _run_batch(force: bool) -> None:
    global _batch_running
    _batch_running = True
    try:
        result = await clip_service.run_batch_embedding(force=force)
        logger.info("CLIP batch done: %s", result)
    finally:
        _batch_running = False


@router.post("/search", summary="文字语义搜索照片")
async def semantic_search(body: SemanticSearchRequest) -> list[dict]:
    if not body.query.strip():
        raise HTTPException(status_code=422, detail="查询词不能为空")

    if not await clip_service.is_available():
        raise HTTPException(status_code=503, detail="CLIP 模型不可用")

    results = await clip_service.search_by_text(body.query, top_k=body.top_k)
    return results


@router.get("/similar/{photo_id}", summary="以图搜图 — 找最相似的照片")
async def find_similar(
    photo_id: int,
    top_k: int = Query(20, ge=1, le=100),
) -> list[dict]:
    if not await clip_service.is_available():
        raise HTTPException(status_code=503, detail="CLIP 模型不可用")

    async with AsyncSessionLocal() as session:
        photo = await session.get(Photo, photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="照片不存在")

    results = await clip_service.search_by_image(photo.file_path, top_k=top_k + 1)
    # Exclude the query photo itself
    return [r for r in results if r["id"] != photo_id][:top_k]
