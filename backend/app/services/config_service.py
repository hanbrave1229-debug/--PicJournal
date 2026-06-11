"""
AppConfig service — singleton row (id=1), lazy-created on first access.
"""
from __future__ import annotations

import time
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_config import AppConfig


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mask_key(key: str) -> str:
    """Return masked version: 'sk-...Ab1c' (last 4 chars visible)."""
    if not key:
        return ""
    visible = key[-4:] if len(key) >= 4 else key
    return f"sk-...{visible}"


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def get_config(db: AsyncSession) -> AppConfig:
    """Return the singleton config row, creating it if absent."""
    result = await db.execute(select(AppConfig).where(AppConfig.id == 1))
    cfg = result.scalar_one_or_none()
    if cfg is None:
        cfg = AppConfig(id=1)
        db.add(cfg)
        await db.commit()
        await db.refresh(cfg)
    return cfg


async def update_config(db: AsyncSession, patch: dict[str, Any]) -> AppConfig:
    cfg = await get_config(db)
    for k, v in patch.items():
        if v is not None and hasattr(cfg, k):
            setattr(cfg, k, v)
    await db.commit()
    await db.refresh(cfg)
    return cfg


# ── Connection test ───────────────────────────────────────────────────────────

_PROVIDER_ENDPOINTS: dict[str, str] = {
    "openai":     "https://api.openai.com/v1/models",
    "anthropic":  "https://api.anthropic.com/v1/models",
    "qianwen":    "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
}


async def test_connection(
    provider: str,
    api_key: str,
    model: str,
    base_url: str | None = None,
) -> dict:
    """
    Lightweight probe — calls the cheapest verification endpoint for each
    provider.  Returns {ok, message, latency_ms}.
    """
    t0 = time.monotonic()

    try:
        if provider == "openai":
            url = (base_url.rstrip("/") + "/models") if base_url else _PROVIDER_ENDPOINTS["openai"]
            headers = {"Authorization": f"Bearer {api_key}"}
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url, headers=headers)
            ok = r.status_code == 200
            msg = "连接成功" if ok else f"HTTP {r.status_code}: {r.text[:120]}"

        elif provider == "anthropic":
            url = _PROVIDER_ENDPOINTS["anthropic"]
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url, headers=headers)
            ok = r.status_code == 200
            msg = "连接成功" if ok else f"HTTP {r.status_code}: {r.text[:120]}"

        elif provider == "qianwen":
            # Minimal text-gen probe — use a tiny prompt
            url = (base_url.rstrip("/")) if base_url else _PROVIDER_ENDPOINTS["qianwen"]
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model or "qwen-turbo",
                "input": {"messages": [{"role": "user", "content": "hi"}]},
                "parameters": {"max_tokens": 1},
            }
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(url, headers=headers, json=payload)
            ok = r.status_code == 200
            msg = "连接成功" if ok else f"HTTP {r.status_code}: {r.text[:120]}"

        elif provider == "custom":
            if not base_url:
                return {"ok": False, "message": "自定义集成商需填写 Base URL", "latency_ms": None}
            url = base_url.rstrip("/") + "/models"
            headers = {"Authorization": f"Bearer {api_key}"}
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url, headers=headers)
            ok = r.status_code in (200, 404)  # 404 = endpoint doesn't exist but key accepted
            msg = "连接成功（兼容 OpenAI 格式）" if ok else f"HTTP {r.status_code}: {r.text[:120]}"

        else:
            return {"ok": False, "message": f"未知集成商: {provider}", "latency_ms": None}

        latency_ms = int((time.monotonic() - t0) * 1000)
        return {"ok": ok, "message": msg, "latency_ms": latency_ms}

    except httpx.ConnectError:
        return {"ok": False, "message": "网络连接失败，请检查网络或代理设置", "latency_ms": None}
    except httpx.TimeoutException:
        return {"ok": False, "message": "请求超时（>10s），服务可能不可达", "latency_ms": None}
    except Exception as e:
        return {"ok": False, "message": f"未知错误: {e}", "latency_ms": None}
