"""
Dedup engine — three-pass duplicate detection pipeline.

Pass 1 — Exact duplicates (MD5)
  Group photos with identical MD5 digests.
  These are byte-for-byte copies regardless of filename or location.

Pass 2 — Perceptual similarity (pHash Hamming distance)
  Photos not already in an exact group are compared pairwise within a
  sliding time window (or globally if EXIF dates are absent).
  Groups are formed with a union-find data structure so chains of
  similar images collapse into a single group.

Pass 3 — Burst shot detection (time + similarity)
  Within a perceptual-similar group, photos taken within N seconds of
  each other (configurable via BURST_INTERVAL_SECONDS) are sub-grouped
  as bursts.  Burst groups surface the recommended keep candidate
  (highest resolution × sharpness) to the UI.

Smart keep recommendation
  For every group the engine nominates one photo to keep using this
  priority order (descending):
    1. Highest resolution (w × h)
    2. Largest file size (better compression ratio / RAW vs JPEG)
    3. Has complete EXIF data (taken_at not null)
    4. Lowest DB id (earliest ingested)
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import timedelta
from typing import TYPE_CHECKING

from app.config import get_settings
from app.core.image_processor import HashResult, compute_hashes
from app.models.duplicate_group import DuplicateType

if TYPE_CHECKING:
    from app.models.photo import Photo

settings = get_settings()


# ── Union-Find (for pHash graph clustering) ───────────────────────────────────

class _UnionFind:
    def __init__(self) -> None:
        self._parent: dict[int, int] = {}

    def find(self, x: int) -> int:
        self._parent.setdefault(x, x)
        if self._parent[x] != x:
            self._parent[x] = self.find(self._parent[x])  # path compression
        return self._parent[x]

    def union(self, x: int, y: int) -> None:
        self._parent[self.find(x)] = self.find(y)

    def groups(self, ids: list[int]) -> dict[int, list[int]]:
        """Return {root_id: [member_ids]} for all IDs that share a root."""
        buckets: dict[int, list[int]] = defaultdict(list)
        for i in ids:
            buckets[self.find(i)].append(i)
        return {root: members for root, members in buckets.items() if len(members) > 1}


# ── Keep recommendation ───────────────────────────────────────────────────────

def _recommend_keep(photos: list[Photo]) -> int:
    """Return the id of the best photo to keep from a duplicate group."""

    def _score(p: Photo) -> tuple:
        resolution = (p.width or 0) * (p.height or 0)
        has_exif = 0 if p.taken_at is None else 1
        return (resolution, p.file_size or 0, has_exif, -(p.id))

    return max(photos, key=_score).id


# ── Hash computation phase ────────────────────────────────────────────────────

async def compute_missing_hashes(
    photos: list[Photo],
    db_session_factory,
) -> None:
    """
    Compute MD5 + pHash for every Photo that is missing either hash,
    then persist the results back to the DB.

    Runs in a ProcessPoolExecutor to saturate all CPU cores.
    """
    from sqlalchemy import update
    from app.models.photo import Photo as PhotoModel

    need_hash = [p for p in photos if p.md5_hash is None or p.phash is None]
    if not need_hash:
        return

    loop = asyncio.get_running_loop()

    with ProcessPoolExecutor(max_workers=settings.worker_processes) as pool:
        futures = [
            loop.run_in_executor(pool, compute_hashes, p.id, p.file_path)
            for p in need_hash
        ]
        results: list[HashResult] = await asyncio.gather(*futures, return_exceptions=True)

    async with db_session_factory() as session:
        for res in results:
            if not isinstance(res, HashResult):
                continue
            await session.execute(
                update(PhotoModel)
                .where(PhotoModel.id == res.photo_id)
                .values(md5_hash=res.md5, phash=res.phash)
            )
        await session.commit()


# ── Pass 1: Exact duplicates ──────────────────────────────────────────────────

def find_exact_duplicates(photos: list[Photo]) -> list[list[Photo]]:
    """
    Group photos by MD5 hash.
    Returns a list of groups; each group has ≥ 2 members.
    """
    buckets: dict[str, list[Photo]] = defaultdict(list)
    for p in photos:
        if p.md5_hash:
            buckets[p.md5_hash].append(p)
    return [group for group in buckets.values() if len(group) >= 2]


# ── Pass 2: Perceptual similarity ─────────────────────────────────────────────

def find_similar_photos(
    photos: list[Photo],
    threshold: int | None = None,
) -> list[list[Photo]]:
    """
    Cluster photos by pHash Hamming distance using union-find.

    Only photos NOT already in an exact-duplicate group are considered
    (caller is responsible for filtering).

    Time complexity: O(n²) pairwise — acceptable up to ~50k photos.
    For very large libraries (> 100k) consider switching to a vantage-point tree.
    """
    from app.core.image_processor import ImageProcessor

    th = threshold if threshold is not None else settings.phash_threshold
    uf = _UnionFind()

    # Build index: photo_id → pHash string
    valid = [p for p in photos if p.phash]

    for i in range(len(valid)):
        for j in range(i + 1, len(valid)):
            dist = ImageProcessor.phash_distance(valid[i].phash, valid[j].phash)  # type: ignore[arg-type]
            if dist is not None and dist <= th:
                uf.union(valid[i].id, valid[j].id)

    id_to_photo = {p.id: p for p in valid}
    groups = uf.groups([p.id for p in valid])

    return [[id_to_photo[pid] for pid in members] for members in groups.values()]


# ── Pass 3: Burst shot detection ──────────────────────────────────────────────

def find_burst_groups(
    similar_group: list[Photo],
    interval_seconds: int | None = None,
) -> list[list[Photo]]:
    """
    Within a perceptual-similar group, sub-divide into burst shots.

    Two photos are in the same burst if:
      - They have EXIF taken_at timestamps, AND
      - The gap between consecutive shots ≤ interval_seconds.

    Returns burst sub-groups (≥ 2 members).  Photos without timestamps
    are excluded from burst grouping.
    """
    interval = interval_seconds if interval_seconds is not None else settings.burst_interval_seconds
    delta = timedelta(seconds=interval)

    dated = sorted(
        [p for p in similar_group if p.taken_at is not None],
        key=lambda p: p.taken_at,  # type: ignore[arg-type, return-value]
    )

    if len(dated) < 2:
        return []

    bursts: list[list[Photo]] = []
    current_burst: list[Photo] = [dated[0]]

    for prev, curr in zip(dated, dated[1:]):
        if (curr.taken_at - prev.taken_at) <= delta:  # type: ignore[operator]
            current_burst.append(curr)
        else:
            if len(current_burst) >= 2:
                bursts.append(current_burst)
            current_burst = [curr]

    if len(current_burst) >= 2:
        bursts.append(current_burst)

    return bursts


# ── Full pipeline ─────────────────────────────────────────────────────────────

class DedupResult:
    """Container returned by run_dedup_pipeline."""

    __slots__ = ("exact_groups", "similar_groups", "burst_groups")

    def __init__(self) -> None:
        self.exact_groups: list[list[Photo]] = []
        self.similar_groups: list[list[Photo]] = []
        self.burst_groups: list[list[Photo]] = []


async def run_dedup_pipeline(
    db_session_factory,
    scan_task_id: int | None = None,
) -> DedupResult:
    """
    Full three-pass dedup pipeline.

    1. Loads all non-deleted photos (optionally scoped to a scan task).
    2. Computes any missing hashes in parallel.
    3. Runs exact → similar → burst detection.
    4. Returns a DedupResult for the service layer to persist.
    """
    from sqlalchemy import select
    from app.models.photo import Photo as PhotoModel

    # ── Load photos ───────────────────────────────────────────────────────────
    async with db_session_factory() as session:
        stmt = select(PhotoModel).where(PhotoModel.is_deleted.is_(False))
        if scan_task_id is not None:
            stmt = stmt.where(PhotoModel.scan_task_id == scan_task_id)
        result = await session.execute(stmt)
        photos: list[Photo] = list(result.scalars().all())

    if not photos:
        return DedupResult()

    # ── Ensure hashes are computed ────────────────────────────────────────────
    await compute_missing_hashes(photos, db_session_factory)

    # Reload with fresh hash values
    async with db_session_factory() as session:
        stmt = select(PhotoModel).where(PhotoModel.is_deleted.is_(False))
        if scan_task_id is not None:
            stmt = stmt.where(PhotoModel.scan_task_id == scan_task_id)
        result = await session.execute(stmt)
        photos = list(result.scalars().all())

    dedup = DedupResult()

    # ── Pass 1: Exact duplicates ──────────────────────────────────────────────
    dedup.exact_groups = find_exact_duplicates(photos)
    exact_ids: set[int] = {p.id for group in dedup.exact_groups for p in group}

    # ── Pass 2: Perceptual similarity (exclude exact dupes) ───────────────────
    non_exact = [p for p in photos if p.id not in exact_ids]
    similar_raw = find_similar_photos(non_exact)

    # ── Pass 3: Burst detection within each similar group ─────────────────────
    burst_ids: set[int] = set()
    for group in similar_raw:
        bursts = find_burst_groups(group)
        if bursts:
            dedup.burst_groups.extend(bursts)
            burst_ids.update(p.id for burst in bursts for p in burst)

    # Similar groups that are NOT pure burst shots
    for group in similar_raw:
        group_ids = {p.id for p in group}
        if not group_ids.issubset(burst_ids):
            dedup.similar_groups.append(group)

    return dedup
