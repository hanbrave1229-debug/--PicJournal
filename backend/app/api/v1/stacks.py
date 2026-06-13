"""
连拍堆叠 API
============
  POST /stacks/auto               — 自动识别全库连拍组
  GET  /stacks/covers             — 所有堆叠封面列表
  GET  /stacks/{stack_id}         — 堆叠内照片详情
  DELETE /stacks/{stack_id}       — 解散堆叠
  POST /stacks/{stack_id}/cover/{photo_id}  — 指定封面
  DELETE /stacks/photos/{photo_id}          — 从堆叠中移除单张
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.services import stack_service

router = APIRouter()

_auto_running = False


@router.post("/auto", summary="自动识别全库连拍组")
async def auto_stack(
    background_tasks: BackgroundTasks,
    dry_run: bool = Query(False, description="仅预览，不写入数据库"),
    force: bool = Query(False, description="重新分析（包含已有 stack_id 的照片）"),
) -> dict:
    global _auto_running
    if _auto_running:
        raise HTTPException(status_code=409, detail="堆叠分析已在运行中")
    if dry_run:
        return await stack_service.auto_stack(dry_run=True)
    _auto_running = True
    background_tasks.add_task(_run_auto)
    return {"status": "started", "message": "连拍堆叠分析已在后台启动"}


async def _run_auto() -> None:
    global _auto_running
    try:
        result = await stack_service.auto_stack(dry_run=False)
        import logging; logging.getLogger(__name__).info("Auto stack done: %s", result)
    finally:
        _auto_running = False


@router.get("/covers", summary="所有堆叠封面照片列表")
async def list_covers() -> list[dict]:
    return await stack_service.list_stack_covers()


@router.get("/{stack_id}", summary="堆叠内照片详情")
async def get_stack(stack_id: str) -> list[dict]:
    photos = await stack_service.get_stack(stack_id)
    if not photos:
        raise HTTPException(status_code=404, detail="堆叠不存在或已为空")
    return photos


@router.delete("/{stack_id}", summary="解散整个堆叠")
async def dissolve_stack(stack_id: str) -> dict:
    count = await stack_service.dissolve_stack(stack_id)
    if count == 0:
        raise HTTPException(status_code=404, detail="堆叠不存在")
    return {"ok": True, "dissolved_count": count}


@router.post("/{stack_id}/cover/{photo_id}", summary="指定堆叠封面")
async def set_cover(stack_id: str, photo_id: int) -> dict:
    ok = await stack_service.set_stack_cover(photo_id)
    if not ok:
        raise HTTPException(status_code=404, detail="照片不存在或不属于任何堆叠")
    return {"ok": True}


@router.delete("/photos/{photo_id}", summary="从堆叠中移除单张照片")
async def unstack_photo(photo_id: int) -> dict:
    ok = await stack_service.unstack(photo_id)
    if not ok:
        raise HTTPException(status_code=404, detail="照片不存在")
    return {"ok": True}
