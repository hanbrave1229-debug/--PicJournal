"""
AI photo tagger — uses a VLM (Vision Language Model) to generate
natural-language captions and keyword tags for photos.

Flow per photo:
  1. Read the 256-px thumbnail from disk (or original if thumbnail missing).
  2. Base64-encode the image.
  3. Call the configured LLM via OpenAI-compatible vision API.
  4. Parse the JSON response → (caption, tags[]).
  5. Write ai_caption + ai_tags back to the Photo row.

The VLM prompt asks for JSON output:
  {"caption": "...", "tags": ["tag1", "tag2", ...]}

Tested with: DeepSeek-VL2, Qwen-VL, GPT-4o-mini vision.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.photo import Photo

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Prompt ────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are a photo analysis assistant. "
    "Analyze the image and respond ONLY with valid JSON (no markdown, no explanation): "
    '{"caption": "<one sentence in Chinese describing the scene>", '
    '"tags": ["tag1", "tag2", ...up to 8 concise Chinese keywords]}'
)

_USER_PROMPT = "Describe this photo."


# ── In-memory progress tracker ────────────────────────────────────────────────

class TaggingProgress:
    """Thread-safe (asyncio) progress state for the current tagging job."""

    def __init__(self) -> None:
        self.running = False
        self.total = 0
        self.done = 0
        self.failed = 0
        self.current_file: str = ""
        self.error: str | None = None

    def to_dict(self) -> dict:
        pct = int(self.done / self.total * 100) if self.total else 0
        return {
            "running": self.running,
            "total": self.total,
            "done": self.done,
            "failed": self.failed,
            "percent": pct,
            "current_file": self.current_file,
            "error": self.error,
        }


# Singleton accessible from the API layer
progress = TaggingProgress()


# ── Image encoding ────────────────────────────────────────────────────────────

def _thumbnail_path(photo: Photo) -> Path | None:
    """Return the 256-px thumbnail path if it exists, else None."""
    if photo.thumbnail_256:
        p = Path(photo.thumbnail_256)
        if p.exists():
            return p
    # Fallback: derive path from convention used by thumbnail_gen.py
    derived = Path(settings.thumbnails_dir) / "256" / f"{photo.id}_256.jpg"
    if derived.exists():
        return derived
    return None


def _encode_image(path: Path) -> tuple[str, str]:
    """Return (base64_data, media_type) for the image at *path*."""
    ext = path.suffix.lower()
    media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(ext, "image/jpeg")

    with path.open("rb") as f:
        data = base64.b64encode(f.read()).decode()
    return data, media_type


# ── Single-photo tagging ──────────────────────────────────────────────────────

async def tag_single_photo(
    photo: Photo,
    db: AsyncSession,
    api_key: str,
    base_url: str,
    model: str,
) -> bool:
    """
    Tag one photo: call VLM → parse → persist.
    Returns True on success, False on failure.
    """
    img_path = _thumbnail_path(photo)
    if img_path is None:
        # No thumbnail available — skip silently
        logger.warning("No thumbnail for photo id=%s, skipping", photo.id)
        return False

    try:
        b64, media_type = _encode_image(img_path)
    except OSError as exc:
        logger.warning("Cannot read thumbnail for photo id=%s: %s", photo.id, exc)
        return False

    url = (base_url.rstrip("/") if base_url else "https://api.openai.com/v1") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 256,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{b64}"},
                    },
                    {"type": "text", "text": _USER_PROMPT},
                ],
            },
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()

        # Strip accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        parsed = json.loads(raw)
        caption: str = parsed.get("caption", "")
        tags: list[str] = parsed.get("tags", [])

        photo.ai_caption = caption[:2048] if caption else None
        photo.ai_tags = json.dumps(tags, ensure_ascii=False) if tags else None
        await db.commit()

        # Write-back to XMP sidecar (non-fatal)
        try:
            from app.services.xmp_service import write_sidecar
            import asyncio as _aio
            loop = _aio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: write_sidecar(
                    photo.file_path,
                    description=photo.ai_caption,
                    tags=tags,
                ),
            )
        except Exception as _xmp_err:
            logger.warning("XMP write-back failed for photo id=%s: %s", photo.id, _xmp_err)

        return True

    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.error("VLM API error for photo id=%s: %s", photo.id, exc)
        return False
    except (json.JSONDecodeError, KeyError) as exc:
        logger.error("VLM response parse error for photo id=%s: %s", photo.id, exc)
        return False


# ── Batch tagging task ────────────────────────────────────────────────────────

async def run_batch_tagging(
    photos: list[Photo],
    db: AsyncSession,
    api_key: str,
    base_url: str,
    model: str,
    concurrency: int = 2,
) -> None:
    """
    Tag all photos in *photos* with up to *concurrency* parallel VLM calls.
    Updates the module-level `progress` singleton throughout.
    """
    global progress
    progress.running = True
    progress.total = len(photos)
    progress.done = 0
    progress.failed = 0
    progress.error = None

    sem = asyncio.Semaphore(concurrency)

    async def _tag_one(photo: Photo) -> None:
        async with sem:
            progress.current_file = photo.file_name
            ok = await tag_single_photo(photo, db, api_key, base_url, model)
            if ok:
                progress.done += 1
            else:
                progress.failed += 1

    try:
        await asyncio.gather(*[_tag_one(p) for p in photos])
    except Exception as exc:
        progress.error = str(exc)
        logger.exception("Batch tagging failed: %s", exc)
    finally:
        progress.running = False
        progress.current_file = ""
