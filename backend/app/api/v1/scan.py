"""
Scan API — trigger and monitor directory scan tasks.

Endpoints:
  POST  /api/v1/scan/start              → create & launch scan
  GET   /api/v1/scan/status/{task_id}   → poll current status
  GET   /api/v1/scan/tasks              → list all scan history
  WS    /api/v1/scan/ws/{task_id}       → real-time progress stream
  POST  /api/v1/scan/tag-photos         → trigger background AI tagging
  GET   /api/v1/scan/tag-status         → poll AI tagging progress
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import scanner
from app.core import ai_tagger
from app.db.database import get_db, AsyncSessionLocal
from app.models.ai_model_config import AiModelConfig
from app.models.photo import Photo
from app.schemas.scan import ScanRequest, ScanStatusResponse
from app.services import scan_service
from app.services.crypto import decrypt

router = APIRouter()


# ── REST ─────────────────────────────────────────────────────────────────────

@router.post("/start", response_model=ScanStatusResponse, summary="Start a scan task")
async def start_scan(
    payload: ScanRequest,
    db: AsyncSession = Depends(get_db),
) -> ScanStatusResponse:
    """
    Start an asynchronous directory scan.
    Returns the created ScanTask ID and initial status immediately;
    actual scanning runs in the background.
    """
    task = await scan_service.create_and_start_scan(payload.scan_path, db)
    return ScanStatusResponse.from_orm_with_progress(task)


@router.get(
    "/status/{task_id}",
    response_model=ScanStatusResponse,
    summary="Get scan task status",
)
async def get_scan_status(
    task_id: int,
    db: AsyncSession = Depends(get_db),
) -> ScanStatusResponse:
    """Return current progress of a running or finished scan task."""
    task = await scan_service.get_scan_task(task_id, db)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Scan task {task_id} not found")
    return ScanStatusResponse.from_orm_with_progress(task)


@router.get("/tasks", response_model=list[ScanStatusResponse], summary="List all scan tasks")
async def list_scan_tasks(
    db: AsyncSession = Depends(get_db),
) -> list[ScanStatusResponse]:
    """Return all historical scan tasks, newest first."""
    tasks = await scan_service.list_scan_tasks(db)
    return [ScanStatusResponse.from_orm_with_progress(t) for t in tasks]


# ── WebSocket ─────────────────────────────────────────────────────────────────

@router.websocket("/ws/{task_id}")
async def scan_progress_ws(task_id: int, websocket: WebSocket) -> None:
    """
    Stream real-time scan progress events for *task_id*.

    Message shape:
      {"event": "progress", "processed": 420, "total": 1000, "pct": 42.0}
      {"event": "completed", "processed": 1000, "total": 1000}
      {"event": "error", "message": "..."}

    The connection closes automatically when the scan finishes or errors.
    """
    await websocket.accept()
    queue = scanner.subscribe(task_id)

    try:
        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send keepalive ping to detect stale connections
                await websocket.send_text(json.dumps({"event": "ping"}))
                continue

            await websocket.send_text(json.dumps(payload))

            # Terminal events — close gracefully after sending
            if payload.get("event") in ("completed", "error"):
                break

    except WebSocketDisconnect:
        pass
    finally:
        scanner.unsubscribe(task_id, queue)
        await websocket.close()


# ── AI Tagging ────────────────────────────────────────────────────────────────

@router.post("/tag-photos", summary="Start AI batch tagging")
async def start_tag_photos(
    limit: int = Query(default=50, ge=1, le=1000, description="Max photos to tag per run"),
    retag: bool = Query(default=False, description="Re-tag photos that already have captions"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Trigger background AI tagging for photos that lack ai_caption.
    Returns immediately; poll /scan/tag-status for progress.

    - limit: max number of photos processed in one run (default 50)
    - retag: if True, overwrites existing ai_caption/ai_tags
    """
    if ai_tagger.progress.running:
        return {"started": False, "reason": "已有打标任务正在运行，请稍后再试"}

    # Read from active AiModelConfig (new multi-config system)
    active_result = await db.execute(
        select(AiModelConfig).where(AiModelConfig.is_active.is_(True))
    )
    active_cfg = active_result.scalar_one_or_none()
    if not active_cfg:
        raise HTTPException(
            status_code=400,
            detail="未选择 AI 模型配置，请在设置页激活一个配置",
        )
    # api_key may be empty for local models (e.g. LM Studio) — that's OK
    api_key  = decrypt(active_cfg.api_key_enc) if active_cfg.api_key_enc else ""
    base_url = active_cfg.base_url or ""
    model    = active_cfg.model or "gpt-4o-mini"
    if not base_url:
        raise HTTPException(
            status_code=400,
            detail=f"配置「{active_cfg.name}」缺少 Base URL，请在设置页补充",
        )

    # Read concurrency from app config
    from app.services.config_service import get_config as _get_app_cfg
    app_cfg = await _get_app_cfg(db)
    vlm_concurrency = app_cfg.vlm_concurrency

    # Fetch photos to tag
    q = select(Photo).where(Photo.is_deleted == False)  # noqa: E712
    if not retag:
        q = q.where(Photo.ai_caption.is_(None))
    q = q.limit(limit)
    result = await db.execute(q)
    photos = list(result.scalars().all())

    if not photos:
        return {"started": False, "reason": "没有需要打标的照片"}

    # Run in background; run_batch_tagging opens its own per-task sessions.
    photo_ids = [p.id for p in photos]

    async def _bg() -> None:
        async with AsyncSessionLocal() as bg_db:
            r = await bg_db.execute(select(Photo).where(Photo.id.in_(photo_ids)))
            bg_photos = list(r.scalars().all())
        await ai_tagger.run_batch_tagging(
            bg_photos, api_key, base_url, model, concurrency=vlm_concurrency,
        )

    asyncio.create_task(_bg())

    return {
        "started": True,
        "total": len(photos),
        "model": model,
    }


@router.get("/tag-status", summary="Poll AI tagging progress")
async def get_tag_status() -> dict:
    """Return current AI tagging progress (no DB needed — in-memory state)."""
    return ai_tagger.progress.to_dict()
