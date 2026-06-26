"""
CLIP 嵌入服务
=============
• 批量为照片生成 512-dim 向量并存入 DB（clip_embedding BLOB）
• 向量索引通过 numpy memmap 文件持久化到磁盘，避免全量加载进 RAM
  — 旧版 np.stack 在 10万张照片时会消耗 ~200MB RAM 并触发 OOM Killer
  — 新版 mmap：读写均通过磁盘映射，常驻内存接近零
• 查询时将 mmap 与查询向量做矩阵乘法，仍走 numpy C++ 路径，性能不损失
"""
from __future__ import annotations

import asyncio
import logging
import os
import struct
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from sqlalchemy import select, text

from app.config import get_settings
from app.db.database import AsyncSessionLocal
from app.models.photo import Photo

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)
settings = get_settings()

# Single-thread executor to avoid blocking the event loop
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="clip")

_DIMS = 512  # CLIP-ViT-B/32 embedding dimension

# Mmap index files on disk — ids (int64) and matrix (float32)
_INDEX_DIR = Path(settings.thumbnails_dir).parent / "db"
_IDS_PATH   = _INDEX_DIR / "clip_ids.npy"
_VECS_PATH  = _INDEX_DIR / "clip_vecs.npy"

# In-process cache: lightweight Python list of IDs + mmap array handle
# The mmap keeps the file descriptor open but does NOT load vectors into RAM.
_index_ids: list[int] = []
_index_mmap: np.ndarray | None = None   # memmap, shape (N, 512), float32
_index_lock = asyncio.Lock()


# ── Public API ─────────────────────────────────────────────────────────────────

async def is_available() -> bool:
    loop = asyncio.get_running_loop()
    from app.core.clip_engine import is_available as _chk
    return await loop.run_in_executor(_executor, _chk)


async def embed_photo(photo_id: int, image_path: str) -> bool:
    """Generate and store embedding for one photo. Returns True on success."""
    loop = asyncio.get_running_loop()
    try:
        from app.core.clip_engine import encode_image
        emb = await loop.run_in_executor(_executor, encode_image, image_path)
        blob = _vec_to_blob(emb)
        async with AsyncSessionLocal() as session:
            photo = await session.get(Photo, photo_id)
            if photo:
                photo.clip_embedding = blob
                await session.commit()
        return True
    except Exception as exc:
        logger.warning("CLIP embed photo %d failed: %s", photo_id, exc)
        return False


async def run_batch_embedding(force: bool = False) -> dict:
    """
    Embed all unembedded photos (or all if force=True).
    Returns progress dict: {total, embedded, failed}.
    """
    async with AsyncSessionLocal() as session:
        stmt = select(
            Photo.id, Photo.file_path, Photo.media_type,
            Photo.thumbnail_1080, Photo.thumbnail_256,
        ).where(Photo.is_deleted.is_(False))
        if not force:
            stmt = stmt.where(Photo.clip_embedding.is_(None))
        rows = (await session.execute(stmt)).all()

    total    = len(rows)
    embedded = 0
    failed   = 0
    logger.info("CLIP batch: %d photos to embed", total)

    for row in rows:
        # CLIP can only read images. For videos, embed the generated keyframe
        # thumbnail (1080 preferred, then 256) so videos are searchable too.
        if row.media_type == "video":
            image_path = row.thumbnail_1080 or row.thumbnail_256
            if not image_path:
                failed += 1
                continue
        else:
            image_path = row.file_path
        ok = await embed_photo(row.id, image_path)
        if ok:
            embedded += 1
        else:
            failed += 1
        await asyncio.sleep(0.1)

    await _rebuild_index()
    return {"total": total, "embedded": embedded, "failed": failed}


async def search_by_text(query: str, top_k: int = 40) -> list[dict]:
    """Return top-k photos most similar to the text query."""
    loop = asyncio.get_running_loop()
    from app.core.clip_engine import encode_text
    text_emb = await loop.run_in_executor(_executor, encode_text, query)
    return await _vector_search(text_emb, top_k)


async def search_by_image(image_path: str, top_k: int = 40) -> list[dict]:
    """Return top-k photos most similar to the query image."""
    loop = asyncio.get_running_loop()
    from app.core.clip_engine import encode_image
    img_emb = await loop.run_in_executor(_executor, encode_image, image_path)
    return await _vector_search(img_emb, top_k)


async def get_status() -> dict:
    async with AsyncSessionLocal() as session:
        total_result  = await session.execute(
            select(text("COUNT(*)")).select_from(Photo).where(Photo.is_deleted.is_(False))
        )
        embedded_result = await session.execute(
            select(text("COUNT(*)")).select_from(Photo)
            .where(Photo.is_deleted.is_(False))
            .where(Photo.clip_embedding.isnot(None))
        )
    total    = total_result.scalar_one()
    embedded = embedded_result.scalar_one()
    return {
        "available": await is_available(),
        "total_photos": total,
        "embedded_photos": embedded,
        "index_size": len(_index_ids),
    }


# ── Internal: disk-mmap index ──────────────────────────────────────────────────

async def _rebuild_index() -> None:
    """
    Rebuild the disk-based mmap index from DB embeddings.

    Memory footprint: O(1) — vectors are written to disk, not stacked in RAM.
    The resulting .npy files are opened with mode='r' (read-only mmap), so the
    OS can page individual rows in/out as needed during search.
    """
    global _index_ids, _index_mmap
    async with _index_lock:
        async with AsyncSessionLocal() as session:
            rows = (await session.execute(
                select(Photo.id, Photo.clip_embedding)
                .where(Photo.is_deleted.is_(False))
                .where(Photo.clip_embedding.isnot(None))
            )).all()

        if not rows:
            _index_ids  = []
            _index_mmap = None
            return

        _INDEX_DIR.mkdir(parents=True, exist_ok=True)

        ids  = []
        # Write vectors row-by-row into a memory-mapped file — no np.stack()
        n = len(rows)
        vecs_mmap = np.lib.format.open_memmap(
            str(_VECS_PATH), mode="w+", dtype=np.float32, shape=(n, _DIMS)
        )
        i = 0
        for photo_id, blob in rows:
            try:
                vec = _blob_to_vec(blob)
                vecs_mmap[i] = vec
                ids.append(photo_id)
                i += 1
            except Exception:
                pass

        # Trim to actual count (skip failed rows)
        if i < n:
            # Re-open with correct shape
            vecs_mmap.flush()
            del vecs_mmap
            final_mmap = np.lib.format.open_memmap(
                str(_VECS_PATH), mode="r+", dtype=np.float32, shape=(i, _DIMS)
            )
            np.lib.format.open_memmap(
                str(_VECS_PATH), mode="w+", dtype=np.float32, shape=(i, _DIMS)
            )[:] = final_mmap[:i]
            del final_mmap

        np.save(str(_IDS_PATH), np.array(ids, dtype=np.int64))

        # Open read-only mmap for queries — OS pages it lazily, RAM usage ≈ 0
        _index_mmap = np.load(str(_VECS_PATH), mmap_mode="r")
        _index_ids  = ids
        logger.info("CLIP mmap index rebuilt: %d vectors → %s", len(ids), _VECS_PATH)


def _load_index_from_disk() -> bool:
    """Try to load a previously built mmap index. Returns True if successful."""
    global _index_ids, _index_mmap
    if not _IDS_PATH.exists() or not _VECS_PATH.exists():
        return False
    try:
        ids_arr = np.load(str(_IDS_PATH))
        _index_ids  = ids_arr.tolist()
        _index_mmap = np.load(str(_VECS_PATH), mmap_mode="r")
        logger.info("CLIP mmap index loaded from disk: %d vectors", len(_index_ids))
        return True
    except Exception as exc:
        logger.warning("Failed to load CLIP mmap index: %s", exc)
        return False


async def _vector_search(query_emb: np.ndarray, top_k: int) -> list[dict]:
    """Cosine similarity search using mmap index — minimal RAM usage."""
    global _index_mmap, _index_ids

    if _index_mmap is None:
        # Try loading from disk first (survives container restarts)
        if not _load_index_from_disk():
            await _rebuild_index()

    if _index_mmap is None or len(_index_ids) == 0:
        return []

    # Matrix multiply: (N, 512) @ (512,) → (N,)
    # numpy reads only the accessed rows from the mmap file via OS page cache
    sims = (_index_mmap @ query_emb).flatten()
    top  = min(top_k, len(_index_ids))
    idxs = np.argpartition(sims, -top)[-top:]
    idxs = idxs[np.argsort(sims[idxs])[::-1]]   # sort desc

    results = [{"photo_id": _index_ids[i], "score": float(sims[i])} for i in idxs]

    photo_ids = [r["photo_id"] for r in results]
    score_map = {r["photo_id"]: r["score"] for r in results}
    async with AsyncSessionLocal() as session:
        photos = (await session.execute(
            select(Photo).where(Photo.id.in_(photo_ids))
        )).scalars().all()

    photo_map = {p.id: p for p in photos}
    out = []
    for pid in photo_ids:
        p = photo_map.get(pid)
        if p:
            out.append({
                "id":            p.id,
                "file_path":     p.file_path,
                "taken_at":      p.taken_at,
                "thumbnail_256": p.thumbnail_256,
                "ai_caption":    p.ai_caption,
                "score":         score_map[pid],
            })
    return out


# ── Serialisation helpers ──────────────────────────────────────────────────────

def _vec_to_blob(v: np.ndarray) -> bytes:
    return struct.pack(f"{len(v)}f", *v.tolist())


def _blob_to_vec(blob: bytes) -> np.ndarray:
    n = len(blob) // 4
    return np.array(struct.unpack(f"{n}f", blob), dtype=np.float32)
