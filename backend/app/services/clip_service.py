"""
CLIP 嵌入服务
=============
• 批量为照片生成 512-dim 向量并存入 DB（clip_embedding BLOB）
• 构建内存索引（numpy 矩阵），支持 cosine-similarity 实时检索
• 优雅降级：CLIP 不可用时返回 available=False，不影响其他功能
"""
from __future__ import annotations

import asyncio
import logging
import struct
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from sqlalchemy import select, text

from app.db.database import AsyncSessionLocal
from app.models.photo import Photo

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Single-thread executor to avoid blocking the event loop
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="clip")

# ── In-memory index ────────────────────────────────────────────────────────────
# Rebuilt after batch embedding; shape (N, 512)
_index_matrix: np.ndarray | None = None
_index_ids: list[int] = []
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
        stmt = select(Photo.id, Photo.file_path).where(Photo.is_deleted.is_(False))
        if not force:
            stmt = stmt.where(Photo.clip_embedding.is_(None))
        rows = (await session.execute(stmt)).all()

    total    = len(rows)
    embedded = 0
    failed   = 0
    logger.info("CLIP batch: %d photos to embed", total)

    for row in rows:
        ok = await embed_photo(row.id, row.file_path)
        if ok:
            embedded += 1
        else:
            failed += 1
        # throttle: 0.1s between photos so NAS stays responsive
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


# ── Internal: index ────────────────────────────────────────────────────────────

async def _rebuild_index() -> None:
    """Load all stored embeddings into a numpy matrix for fast cosine search."""
    global _index_matrix, _index_ids
    async with _index_lock:
        async with AsyncSessionLocal() as session:
            rows = (await session.execute(
                select(Photo.id, Photo.clip_embedding)
                .where(Photo.is_deleted.is_(False))
                .where(Photo.clip_embedding.isnot(None))
            )).all()

        if not rows:
            _index_matrix = None
            _index_ids = []
            return

        ids  = []
        vecs = []
        for photo_id, blob in rows:
            try:
                vec = _blob_to_vec(blob)
                ids.append(photo_id)
                vecs.append(vec)
            except Exception:
                pass

        _index_ids    = ids
        _index_matrix = np.stack(vecs, axis=0).astype(np.float32)   # (N, 512)
        logger.info("CLIP index rebuilt: %d vectors", len(ids))


async def _vector_search(query_emb: np.ndarray, top_k: int) -> list[dict]:
    """Cosine similarity search in the in-memory index."""
    global _index_matrix, _index_ids

    if _index_matrix is None:
        await _rebuild_index()

    if _index_matrix is None or len(_index_ids) == 0:
        return []

    sims = (_index_matrix @ query_emb).flatten()             # (N,)
    top  = min(top_k, len(_index_ids))
    idxs = np.argpartition(sims, -top)[-top:]
    idxs = idxs[np.argsort(sims[idxs])[::-1]]               # sort desc

    results = []
    for i in idxs:
        results.append({
            "photo_id": _index_ids[i],
            "score":    float(sims[i]),
        })

    # Fetch full photo info
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
    """Pack float32 array to raw bytes."""
    return struct.pack(f"{len(v)}f", *v.tolist())


def _blob_to_vec(blob: bytes) -> np.ndarray:
    n = len(blob) // 4
    return np.array(struct.unpack(f"{n}f", blob), dtype=np.float32)
