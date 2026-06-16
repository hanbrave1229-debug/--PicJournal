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
    "You are a photo analysis assistant. Look at the actual image content and "
    "respond ONLY with valid JSON, no markdown, no explanation, no placeholders. "
    "The JSON must have exactly two keys: \"caption\" (one Chinese sentence describing "
    "what is actually in the photo) and \"tags\" (a JSON array of up to 8 concise Chinese "
    "keywords describing the photo). "
    "Example of the exact format (do NOT reuse this content, describe the real image instead): "
    '{"caption": "夕阳下的海边沙滩，几只海鸥在飞翔", "tags": ["海滩", "夕阳", "海鸥", "大海"]}'
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
        self.last_failure: str | None = None  # detail of the most recent per-photo failure

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
            "last_failure": self.last_failure,
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


async def _ensure_thumbnail(photo: Photo, db: AsyncSession) -> Path | None:
    """
    Regenerate the 256-px thumbnail on demand if it is missing on disk.
    Mirrors the on-demand logic in the thumbnails API endpoint so tagging
    self-heals when the thumbnails volume was wiped but originals remain.
    Returns the thumbnail Path, or None if regeneration is impossible.
    """
    try:
        from app.core.thumbnail_gen import generate_thumbnails

        source_path = photo.file_path
        if getattr(photo, "media_type", "photo") == "video":
            return None  # videos: skip on-demand regen here
        if not source_path or not Path(source_path).exists():
            return None

        results = await generate_thumbnails(source_path, photo.id)
        thumb = results.get(256)
        if thumb and Path(thumb).exists():
            photo.thumbnail_256 = thumb
            await db.commit()
            return Path(thumb)
    except Exception as exc:  # noqa: BLE001 — non-fatal, just report
        logger.warning("On-demand thumbnail regen failed for id=%s: %s", photo.id, exc)
    return None


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
        # Thumbnail file missing on disk (e.g. thumbnails volume not persisted).
        # Try to regenerate on-demand from the original file before giving up.
        img_path = await _ensure_thumbnail(photo, db)
    if img_path is None:
        msg = f"缩略图缺失且无法生成: id={photo.id} {photo.file_name}"
        logger.warning(msg)
        progress.last_failure = msg
        return False

    try:
        b64, media_type = _encode_image(img_path)
    except OSError as exc:
        msg = f"缩略图读取失败: id={photo.id} {exc}"
        logger.warning(msg)
        progress.last_failure = msg
        return False

    url = (base_url.rstrip("/") if base_url else "https://api.openai.com/v1") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # Merge system prompt into user message for compatibility with local models
    # that don't support the `system` role (e.g. LM Studio, Ollama).
    combined_user = (
        _SYSTEM_PROMPT + "\n\n" + _USER_PROMPT
    )
    payload = {
        "model": model,
        "max_tokens": 512,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{b64}"},
                    },
                    {"type": "text", "text": combined_user},
                ],
            },
        ],
    }

    try:
        # trust_env=False: ignore HTTP_PROXY/HTTPS_PROXY env vars so a LAN /
        # self-hosted model endpoint (e.g. LM Studio) is reached directly
        # instead of being routed through the host's global proxy.
        async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if not resp.is_success and "response_format" in resp.text:
                # Backend doesn't support response_format (e.g. some LM Studio
                # builds) — retry once without it.
                payload.pop("response_format", None)
                resp = await client.post(url, headers=headers, json=payload)
        if not resp.is_success:
            err_body = resp.text[:300]
            logger.error(
                "VLM HTTP %s for photo id=%s: %s", resp.status_code, photo.id, err_body
            )
            progress.last_failure = f"HTTP {resp.status_code}: {err_body}"
            return False

        msg = resp.json()["choices"][0]["message"]
        content_text = msg.get("content") or ""
        reasoning_text = msg.get("reasoning_content") or ""

        import re as _re

        def _extract_json_obj(text: str) -> dict | None:
            # Try all top-level {...} blocks (last first — model puts answer at end)
            for m in reversed(list(_re.finditer(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}", text, _re.DOTALL))):
                try:
                    d = json.loads(m.group(0))
                    if "caption" in d or "tags" in d:
                        return d
                except Exception:
                    pass
            # Greedy fallback: outermost {...}
            m = _re.search(r"\{.*\}", text, _re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    pass
            return None

        parsed = _extract_json_obj(content_text) or _extract_json_obj(reasoning_text)
        if parsed is not None:
            caption: str = parsed.get("caption", "")
            tags: list[str] = parsed.get("tags", [])
        else:
            # Model ignored the JSON instruction and replied with free-form
            # prose. Fall back to using that prose as the caption directly
            # rather than discarding the photo outright.
            raw = (content_text or reasoning_text).strip()
            if not raw:
                raise json.JSONDecodeError("empty response", "", 0)
            caption = _re.sub(r"\s+", " ", raw)[:500]
            tags = []

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

    except httpx.RequestError as exc:
        msg = f"连接失败: {exc}"
        logger.error("VLM request error for photo id=%s: %s", photo.id, exc)
        progress.last_failure = msg
        return False
    except (json.JSONDecodeError, KeyError) as exc:
        msg = f"响应解析失败: {exc} | raw={raw[:200] if 'raw' in dir() else 'N/A'}"
        logger.error("VLM response parse error for photo id=%s: %s", photo.id, exc)
        progress.last_failure = msg
        return False


# ── Batch tagging task ────────────────────────────────────────────────────────

async def run_batch_tagging(
    photos: list[Photo],
    api_key: str,
    base_url: str,
    model: str,
    concurrency: int = 1,
) -> None:
    """
    Tag all photos in *photos* with up to *concurrency* parallel VLM calls.
    Updates the module-level `progress` singleton throughout.

    Each concurrent task uses its OWN database session — an AsyncSession must
    never be shared across concurrent coroutines (it is not concurrency-safe;
    sharing one corrupts its state and triggers "database is locked").
    """
    from app.db.database import AsyncSessionLocal

    global progress
    progress.running = True
    progress.total = len(photos)
    progress.done = 0
    progress.failed = 0
    progress.error = None

    # Capture ids up front; the caller's session/objects are not reused here.
    photo_ids = [p.id for p in photos]
    sem = asyncio.Semaphore(max(1, concurrency))

    async def _tag_one(pid: int) -> None:
        async with sem:
            async with AsyncSessionLocal() as task_db:
                photo = await task_db.get(Photo, pid)
                if photo is None:
                    progress.failed += 1
                    return
                progress.current_file = photo.file_name
                ok = await tag_single_photo(photo, task_db, api_key, base_url, model)
            if ok:
                progress.done += 1
                progress.last_failure = None  # clear on success streak
            else:
                progress.failed += 1

    try:
        await asyncio.gather(*[_tag_one(pid) for pid in photo_ids])
    except Exception as exc:
        progress.error = str(exc)
        logger.exception("Batch tagging failed: %s", exc)
    finally:
        progress.running = False
        progress.current_file = ""
