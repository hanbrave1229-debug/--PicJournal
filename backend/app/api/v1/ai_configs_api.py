"""
ai_configs_api.py — CRUD + activate for AI model configurations.

Rules:
- api_key stored encrypted; never returned in plaintext
- Activating a config deactivates all others (atomic transaction)
- Deleting the active config is allowed; caller should activate another
"""
from __future__ import annotations

import time

import httpx
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
from app.services.key_exchange import get_public_key_spki_b64, rsa_decrypt

router = APIRouter()


def _resolve_plaintext_key(api_key_cipher: str | None, api_key: str | None) -> str | None:
    """
    Return the plaintext API key from either the RSA-OAEP cipher or the legacy plaintext field.
    Returns None if neither is provided (meaning: keep existing key unchanged).
    """
    if api_key_cipher:
        try:
            return rsa_decrypt(api_key_cipher)
        except Exception:
            raise HTTPException(status_code=400, detail="api_key_cipher 解密失败，请重新获取公钥后再试")
    return api_key or None


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


# ── Public key for client-side encryption ─────────────────────────────────────

@router.get("/pubkey", summary="获取 RSA 公钥（SPKI/DER base64），用于前端加密 API Key")
async def get_pubkey() -> dict:
    """
    Returns the ephemeral RSA-2048 public key in SPKI/DER base64 format.
    The frontend imports this with SubtleCrypto and encrypts the API key with
    RSA-OAEP / SHA-256 before sending. The private key never leaves the server.
    """
    return {"pubkey": get_public_key_spki_b64(), "algorithm": "RSA-OAEP", "hash": "SHA-256"}


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
    plaintext_key = _resolve_plaintext_key(body.api_key_cipher, body.api_key) or ""
    cfg = AiModelConfig(
        name=body.name,
        provider=body.provider,
        api_key_enc=encrypt(plaintext_key),
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
    # Only update key if a new value is provided (cipher takes precedence)
    new_key = _resolve_plaintext_key(body.api_key_cipher, body.api_key)
    if new_key:
        cfg.api_key_enc = encrypt(new_key)

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


# ── Test connectivity ─────────────────────────────────────────────────────────

@router.post("/{config_id}/test")
async def test_config(config_id: int, db: AsyncSession = Depends(get_db)):
    """
    Send a minimal text-only chat request to verify the endpoint is reachable
    and the API key is accepted. Returns latency_ms on success.
    """
    cfg = await db.get(AiModelConfig, config_id)
    if not cfg:
        raise HTTPException(404, "Config not found")

    from app.services.crypto import decrypt
    api_key  = decrypt(cfg.api_key_enc) if cfg.api_key_enc else ""
    if not api_key.strip():
        return {"ok": False, "latency_ms": None, "error": "未配置 API Key，请先编辑并填写密钥"}

    base_url = (cfg.base_url or "https://api.openai.com/v1").rstrip("/")
    model    = cfg.model

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 1,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
        latency_ms = int((time.monotonic() - t0) * 1000)

        if resp.status_code in (200, 201):
            return {"ok": True, "latency_ms": latency_ms, "status_code": resp.status_code}

        # Parse error message from response body if possible
        try:
            err = resp.json().get("error", {}).get("message", resp.text[:200])
        except Exception:
            err = resp.text[:200]
        return {"ok": False, "latency_ms": latency_ms, "status_code": resp.status_code, "error": err}

    except httpx.ConnectError as e:
        return {"ok": False, "latency_ms": None, "error": f"无法连接: {base_url}"}
    except httpx.TimeoutException:
        return {"ok": False, "latency_ms": None, "error": "连接超时（10s）"}
    except Exception as e:
        return {"ok": False, "latency_ms": None, "error": str(e)}


# ── Get active (for internal health checks / UI badge) ────────────────────────

@router.get("/active", response_model=AiModelConfigResponse | None)
async def get_active_config(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AiModelConfig).where(AiModelConfig.is_active.is_(True))
    )
    cfg = result.scalar_one_or_none()
    return _to_response(cfg) if cfg else None
