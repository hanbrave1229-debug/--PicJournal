"""
App config API — AI provider settings.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.config import (
    AIConfigResponse,
    AIConfigUpdate,
    ConnectionTestRequest,
    ConnectionTestResponse,
)
from app.services import config_service

router = APIRouter()


@router.get("", response_model=AIConfigResponse)
async def get_config(db: AsyncSession = Depends(get_db)):
    """Return current AI config. api_key is always masked."""
    cfg = await config_service.get_config(db)
    return AIConfigResponse(
        ai_provider=cfg.ai_provider,
        ai_api_key_masked=config_service._mask_key(cfg.ai_api_key),
        ai_model=cfg.ai_model,
        ai_base_url=cfg.ai_base_url,
        ai_enabled=cfg.ai_enabled,
        ai_auto_tag=cfg.ai_auto_tag,
        ai_batch_size=cfg.ai_batch_size,
        face_min_photos=cfg.face_min_photos,
        vlm_concurrency=cfg.vlm_concurrency,
    )


@router.patch("", response_model=AIConfigResponse)
async def update_config(
    body: AIConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Partial update. Pass ai_api_key only when the user explicitly changes it."""
    patch = body.model_dump(exclude_none=True)
    cfg = await config_service.update_config(db, patch)
    return AIConfigResponse(
        ai_provider=cfg.ai_provider,
        ai_api_key_masked=config_service._mask_key(cfg.ai_api_key),
        ai_model=cfg.ai_model,
        ai_base_url=cfg.ai_base_url,
        ai_enabled=cfg.ai_enabled,
        ai_auto_tag=cfg.ai_auto_tag,
        ai_batch_size=cfg.ai_batch_size,
        face_min_photos=cfg.face_min_photos,
        vlm_concurrency=cfg.vlm_concurrency,
    )


@router.post("/test", response_model=ConnectionTestResponse)
async def test_connection(body: ConnectionTestRequest):
    """
    Test connectivity with the provided credentials — does NOT save them.
    Frontend calls this before/after saving to verify the key works.
    """
    result = await config_service.test_connection(
        provider=body.provider,
        api_key=body.api_key,
        model=body.model,
        base_url=body.base_url,
    )
    return ConnectionTestResponse(**result)
