"""
ai_configs_api.py — CRUD + activate for AI model configurations.

Rules:
- api_key stored encrypted; never returned in plaintext
- Activating a config deactivates all others (atomic transaction)
- Deleting the active config is allowed; caller should activate another
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.ai_model_config import AiModelConfig
from app.schemas.ai_model_config import (
    AiModelConfigCreate,
    AiModelConfigResponse,
    AiModelConfigUpdate,
)
from app.services.crypto import decrypt, encrypt, mask_key

router = APIRouter()


def _to_response(cfg: AiModelConfig) -> AiModelConfigResponse:
    return AiModelConfigResponse(
        id=cfg.id,
        name=cfg.name,
        provider=cfg.provider,
        api_key_masked=mask_key(cfg.api_key_enc),
        base_url=cfg.base_url,
        model=cfg.model,
        is_active=cfg.is_active,
        created_at=cfg.created_at,
        updated_at=cfg.updated_at,
    )


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[AiModelConfigResponse])
async def list_configs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AiModelConfig).order_by(AiModelConfig.created_at)
    )
    return [_to_response(c) for c in result.scalars().all()]


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", response_model=AiModelConfigResponse, status_code=201)
async def create_config(body: AiModelConfigCreate, db: AsyncSession = Depends(get_db)):
    cfg = AiModelConfig(
        name=body.name,
        provider=body.provider,
        api_key_enc=encrypt(body.api_key),
        base_url=body.base_url or None,
        model=body.model,
        is_active=False,
    )
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    return _to_response(cfg)


# ── Update ────────────────────────────────────────────────────────────────────

@router.put("/{config_id}", response_model=AiModelConfigResponse)
async def update_config(
    config_id: int,
    body: AiModelConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    cfg = await db.get(AiModelConfig, config_id)
    if not cfg:
        raise HTTPException(404, "Config not found")

    if body.name is not None:
        cfg.name = body.name
    if body.provider is not None:
        cfg.provider = body.provider
    if body.base_url is not None:
        cfg.base_url = body.base_url or None
    if body.model is not None:
        cfg.model = body.model
    # Only update key if a non-empty value is provided
    if body.api_key:
        cfg.api_key_enc = encrypt(body.api_key)

    await db.commit()
    await db.refresh(cfg)
    return _to_response(cfg)


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{config_id}", status_code=204)
async def delete_config(config_id: int, db: AsyncSession = Depends(get_db)):
    cfg = await db.get(AiModelConfig, config_id)
    if not cfg:
        raise HTTPException(404, "Config not found")
    await db.delete(cfg)
    await db.commit()


# ── Activate ──────────────────────────────────────────────────────────────────

@router.post("/{config_id}/activate", response_model=AiModelConfigResponse)
async def activate_config(config_id: int, db: AsyncSession = Depends(get_db)):
    cfg = await db.get(AiModelConfig, config_id)
    if not cfg:
        raise HTTPException(404, "Config not found")

    # Deactivate all others in one statement, then activate the target
    await db.execute(
        update(AiModelConfig)
        .where(AiModelConfig.id != config_id)
        .values(is_active=False)
    )
    cfg.is_active = True
    await db.commit()
    await db.refresh(cfg)
    return _to_response(cfg)


# ── Get active (for internal health checks / UI badge) ────────────────────────

@router.get("/active", response_model=AiModelConfigResponse | None)
async def get_active_config(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AiModelConfig).where(AiModelConfig.is_active.is_(True))
    )
    cfg = result.scalar_one_or_none()
    return _to_response(cfg) if cfg else None
