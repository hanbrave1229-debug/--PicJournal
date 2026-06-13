"""
vision_llm.py — Multimodal vision analysis via any OpenAI-compatible endpoint.

Base URL and model are read from AppConfig (same row used by diary AI).
Configure in the frontend Settings → AI 集成 page.
"""
import base64
import logging
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_model_config import AiModelConfig
from app.services.crypto import decrypt

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 120  # seconds


async def _get_vision_config(db: AsyncSession) -> tuple[str, str, str]:
    """
    Return (base_url, model, api_key_plaintext) from the active AiModelConfig.
    Raises RuntimeError if none is active or config is incomplete.
    """
    result = await db.execute(
        select(AiModelConfig).where(AiModelConfig.is_active.is_(True))
    )
    cfg = result.scalar_one_or_none()

    if not cfg:
        raise RuntimeError("未选择 AI 模型配置，请在设置页激活一个配置")

    base_url = (cfg.base_url or "").rstrip("/")
    model    = cfg.model or ""
    api_key  = decrypt(cfg.api_key_enc)

    if not base_url:
        raise RuntimeError(f"配置「{cfg.name}」缺少 Base URL，请在设置页补充")
    if not model:
        raise RuntimeError(f"配置「{cfg.name}」缺少模型名称，请在设置页补充")

    return base_url, model, api_key


def _encode_image(path: str | Path) -> tuple[str, str]:
    """Return (base64_data, mime_type) for a local image file."""
    p = Path(path)
    suffix = p.suffix.lower()
    mime = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png",  ".webp": "image/webp",
        ".gif": "image/gif",  ".heic": "image/heic",
    }.get(suffix, "image/jpeg")
    data = base64.b64encode(p.read_bytes()).decode()
    return data, mime


async def analyze_photo(
    image_path: str | Path,
    prompt: str,
    db: AsyncSession,
) -> str:
    """
    Send an image + text prompt to the configured vision model and return the response.
    Returns empty string on any error so callers can degrade gracefully.
    """
    try:
        b64, mime = _encode_image(image_path)
    except Exception as e:
        logger.warning("vision_llm: failed to read image %s: %s", image_path, e)
        return ""

    try:
        base_url, model, api_key = await _get_vision_config(db)
    except RuntimeError as e:
        logger.warning("vision_llm: %s", e)
        return ""

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        }],
        "max_tokens": 512,
        "temperature": 0.3,
    }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            res = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            res.raise_for_status()
            return res.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning("vision_llm: request failed: %s", e)
        return ""


# ── Preset prompts for PicJournal features ────────────────────────────────────

async def caption_photo(image_path: str | Path, db: AsyncSession) -> str:
    """Generate a concise Chinese description of the photo."""
    return await analyze_photo(
        image_path,
        "用一到两句中文描述这张照片的主要内容，包括场景、人物（如有）、情感氛围。不要加前缀。",
        db,
    )


async def tag_photo(image_path: str | Path, db: AsyncSession) -> list[str]:
    """Return a list of Chinese keyword tags for the photo."""
    raw = await analyze_photo(
        image_path,
        "为这张照片生成5到10个中文标签，用逗号分隔，只输出标签，不要其他内容。"
        "例如：海边,日落,家庭,儿童,夏天",
        db,
    )
    if not raw:
        return []
    return [t.strip() for t in raw.replace("、", ",").split(",") if t.strip()]


async def ocr_photo(image_path: str | Path, db: AsyncSession) -> str:
    """Extract text visible in the photo (OCR)."""
    return await analyze_photo(
        image_path,
        "请提取并输出图片中所有可见的文字，保持原有排版，没有文字则回复「无」。",
        db,
    )


async def recognize_landmark(image_path: str | Path, db: AsyncSession) -> str:
    """Identify landmark or location visible in the photo."""
    return await analyze_photo(
        image_path,
        "如果图片中有可识别的地标、建筑或著名地点，请说出名称和所在城市/国家。"
        "如果无法识别，回复「无法识别」。只输出结论，不要解释。",
        db,
    )


async def write_journal_entry(image_path: str | Path, date_str: str, db: AsyncSession) -> str:
    """Generate a short diary entry in first person for a photo."""
    return await analyze_photo(
        image_path,
        f"这是{date_str}拍摄的一张照片。请以第一人称，用温暖自然的语气，"
        "写一段100字以内的手账日记，描述当时的场景和心情。",
        db,
    )
