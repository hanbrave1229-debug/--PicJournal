"""
Async thumbnail generator.

Design decisions:
  - Thumbnail generation is CPU-bound (Pillow resize). It is offloaded to a
    ThreadPoolExecutor so it never blocks the FastAPI event loop.
  - We generate two sizes: 256 px and 1080 px (short-edge constrained).
  - Output format is always JPEG for small file size; EXIF orientation is
    applied so the browser never needs to rotate.
  - Thumbnails are named by photo DB id:  <id>_256.jpg  /  <id>_1080.jpg
  - If a thumbnail file already exists it is NOT regenerated (idempotent).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from app.config import get_settings

settings = get_settings()


# ── Sync worker (runs in ThreadPoolExecutor) ─────────────────────────────────

def _generate_thumbnail_sync(
    source_path: str,
    photo_id: int,
    size: int,
    thumbnails_dir: str,
) -> str | None:
    """
    Open *source_path*, resize to *size* px (short edge), and save as JPEG.

    Returns the relative path of the thumbnail, or None on failure.
    """
    try:
        from PIL import Image, ImageOps

        dest_dir = Path(thumbnails_dir) / str(size)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / f"{photo_id}_{size}.jpg"

        if dest_path.exists():
            return str(dest_path)

        with Image.open(source_path) as img:
            # Apply EXIF orientation (e.g. portrait shots from phones)
            img = ImageOps.exif_transpose(img)

            # Convert to RGB — required for JPEG output (drops alpha, handles palette)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            # Resize: constrain short edge to `size`, keep aspect ratio
            w, h = img.size
            if w < h:
                new_w = size
                new_h = int(h * size / w)
            else:
                new_h = size
                new_w = int(w * size / h)

            img = img.resize((new_w, new_h), Image.LANCZOS)

            img.save(dest_path, "JPEG", quality=82, optimize=True, progressive=True)

        return str(dest_path)

    except Exception:
        return None


# ── Public async API ──────────────────────────────────────────────────────────

async def generate_thumbnails(
    source_path: str,
    photo_id: int,
) -> dict[int, str | None]:
    """
    Generate all configured thumbnail sizes for a photo.

    Returns a dict mapping size (px) → thumbnail file path (or None on failure).
    Non-blocking: Pillow work runs in the default ThreadPoolExecutor.
    """
    loop = asyncio.get_running_loop()
    results: dict[int, str | None] = {}

    tasks = [
        loop.run_in_executor(
            None,  # default ThreadPoolExecutor
            _generate_thumbnail_sync,
            source_path,
            photo_id,
            size,
            settings.thumbnails_dir,
        )
        for size in settings.thumbnail_sizes
    ]

    for size, result in zip(settings.thumbnail_sizes, await asyncio.gather(*tasks)):
        results[size] = result

    return results


async def generate_thumbnails_batch(
    items: list[tuple[str, int]],
) -> list[dict[int, str | None]]:
    """
    Generate thumbnails for a batch of (source_path, photo_id) pairs concurrently.

    More efficient than calling generate_thumbnails() in a loop because all
    resize operations are submitted to the thread pool at once.
    """
    return list(await asyncio.gather(*[
        generate_thumbnails(path, photo_id)
        for path, photo_id in items
    ]))
