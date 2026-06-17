"""
Face analysis service — orchestrates detection, clustering, and persistence.

Pipeline:
  1. Load all non-deleted photos from DB.
  2. Detect faces in each photo using face_engine.detect_faces_in_image().
  3. Cluster all detected embeddings with DBSCAN.
  4. Persist FaceCrop rows; create/update Person rows; save face crop images.
  5. Return a FaceRunResponse summary.

Thread-safety: a module-level lock prevents concurrent runs.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import time
from pathlib import Path

from sqlalchemy import delete, func, select

from app.config import get_settings
from app.core.face_engine import (
    EMBEDDING_DIM,
    FACE_RECOGNITION_AVAILABLE,
    SKLEARN_AVAILABLE,
    ClusteredFace,
    DetectedFace,
    cluster_faces,
    detect_faces_in_image,
    embedding_to_str,
    save_face_crop,
)
from app.db.database import AsyncSessionLocal
from app.models.person import FaceCrop, Person
from app.models.photo import Photo
from app.schemas.person import FaceRunResponse

logger = logging.getLogger(__name__)
settings = get_settings()

_running_lock = asyncio.Lock()
_last_result: FaceRunResponse | None = None
_is_running: bool = False

# CPU-bound detection: single worker prevents NAS core saturation.
_face_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="face")
# I/O-bound crop saves: separate pool so saves don't queue behind detection.
_crop_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="crop")


# ── Public API ────────────────────────────────────────────────────────────────

async def get_status() -> dict:
    return {"running": _is_running, "last_run_result": _last_result}


def start_face_analysis(force: bool = False) -> None:
    """
    Non-blocking entry point: validate state, then fire an asyncio background task.
    Returns immediately — caller should poll /persons/status for progress.
    Raises RuntimeError (→ 409) if preconditions fail or already running.
    """
    if not FACE_RECOGNITION_AVAILABLE:
        raise RuntimeError(
            "insightface 或 onnxruntime 未正确安装。"
            "请拉取最新 Docker 镜像（docker compose pull && docker compose up -d）。"
        )
    if not SKLEARN_AVAILABLE:
        raise RuntimeError("scikit-learn 未安装，无法执行人脸聚类。")
    if _is_running:
        raise RuntimeError("Face analysis already running")

    asyncio.create_task(_run_in_background(force=force))


async def _run_in_background(force: bool) -> None:
    """Internal background coroutine — updates _is_running / _last_result."""
    global _is_running, _last_result
    async with _running_lock:
        _is_running = True
        try:
            result = await _pipeline(force=force)
            _last_result = result
        except Exception as exc:
            logger.error("Face analysis pipeline error: %s", exc, exc_info=True)
        finally:
            _is_running = False


async def run_face_analysis(force: bool = False) -> FaceRunResponse:
    """
    Blocking entry (kept for internal/test use). Use start_face_analysis() from API.
    """
    global _is_running, _last_result

    if not FACE_RECOGNITION_AVAILABLE:
        raise RuntimeError("insightface 未安装")
    if not SKLEARN_AVAILABLE:
        raise RuntimeError("scikit-learn 未安装")
    if _is_running:
        raise RuntimeError("Face analysis already running")

    async with _running_lock:
        _is_running = True
        try:
            result = await _pipeline(force=force)
        finally:
            _is_running = False
        _last_result = result
        return result


# ── Internal pipeline ─────────────────────────────────────────────────────────

async def _pipeline(force: bool) -> FaceRunResponse:
    faces_dir = Path(settings.thumbnails_dir) / "faces"
    faces_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. Load photos ─────────────────────────────────────────────────────────
    async with AsyncSessionLocal() as session:
        stmt = select(Photo.id, Photo.file_path).where(Photo.is_deleted.is_(False))

        if not force:
            # Skip photos already face-analyzed (true checkpoint — works even if no faces found)
            stmt = stmt.where(Photo.face_analyzed_at.is_(None))

        rows = (await session.execute(stmt)).all()

    if not rows:
        return FaceRunResponse(
            photos_processed=0,
            faces_detected=0,
            persons_created=0,
            persons_updated=0,
            message="No new photos to process",
        )

    logger.info("Face analysis: processing %d photos", len(rows))

    # ── 2. Detect faces (run in thread pool to avoid blocking event loop) ──────
    loop = asyncio.get_running_loop()
    all_faces: list[DetectedFace] = []

    def _detect_with_throttle(photo_id: int, image_path: str) -> list:
        """在 executor 内检测完后睡眠 0.2s，强制限制 CPU 占用率上限。"""
        result = detect_faces_in_image(photo_id, image_path)
        time.sleep(0.2)   # 硬性节流：每张照片检测完休眠 200ms，CPU 峰值约降 30-40%
        return result

    for i, row in enumerate(rows):
        faces = await loop.run_in_executor(
            _face_executor, _detect_with_throttle, row.id, row.file_path
        )
        all_faces.extend(faces)

        # 每检测完一张立即写入 face_analyzed_at — 断点续传的核心：重启后跳过已检测的照片
        async with AsyncSessionLocal() as session:
            photo = await session.get(Photo, row.id)
            if photo:
                photo.face_analyzed_at = func.now()
                await session.commit()

        # 每 5 张让出一次事件循环，保持其他 API 请求响应性
        if i % 5 == 0:
            await asyncio.sleep(0)

    logger.info("Face analysis: detected %d faces", len(all_faces))

    if not all_faces:
        return FaceRunResponse(
            photos_processed=len(rows),
            faces_detected=0,
            persons_created=0,
            persons_updated=0,
            message="No faces detected",
        )

    # ── 3. Load existing embeddings for incremental clustering ─────────────────
    async with AsyncSessionLocal() as session:
        existing_crops = (
            await session.execute(
                select(
                    FaceCrop.id,
                    FaceCrop.photo_id,
                    FaceCrop.bbox_top, FaceCrop.bbox_right,
                    FaceCrop.bbox_bottom, FaceCrop.bbox_left,
                    FaceCrop.embedding, FaceCrop.person_id,
                )
            )
        ).all()

    existing_faces: list[DetectedFace] = []
    existing_person_ids: list[int | None] = []  # parallel to existing_faces
    for c in existing_crops:
        # Only include embeddings with matching dimension (skip legacy 128-dim from face_recognition)
        if not c.embedding or len(c.embedding.split(",")) != EMBEDDING_DIM:
            continue
        existing_faces.append(
            DetectedFace(
                photo_id=c.photo_id,
                bbox_top=c.bbox_top,
                bbox_right=c.bbox_right,
                bbox_bottom=c.bbox_bottom,
                bbox_left=c.bbox_left,
                embedding=[float(v) for v in c.embedding.split(",")],
            )
        )
        existing_person_ids.append(c.person_id)

    combined_faces = existing_faces + all_faces

    # ── 4. Re-cluster all embeddings (CPU-heavy — must run in thread pool) ─────
    clustered: list[ClusteredFace] = await loop.run_in_executor(
        _face_executor, cluster_faces, combined_faces
    )

    # Split the re-clustered result back into the existing and new portions.
    existing_clustered = clustered[:len(existing_faces)]
    new_clustered = clustered[len(existing_faces):]

    # ── 5. Map cluster labels → Person rows ────────────────────────────────────
    #
    # Incremental clustering: a DBSCAN label may already contain faces that were
    # assigned to a Person in a previous run. New faces sharing that label MUST
    # reuse the existing person_id instead of spawning a duplicate Person —
    # otherwise every /run re-creates everybody and the person list explodes.
    async with AsyncSessionLocal() as session:
        # Seed the mapping from already-persisted faces: label → existing person_id.
        label_to_person_id: dict[int, int] = {}
        for face, person_id in zip(existing_clustered, existing_person_ids):
            label = face["cluster_label"]
            if label == -1 or person_id is None:
                continue
            label_to_person_id.setdefault(label, person_id)

        # Determine how many persons already exist (for naming new ones).
        existing_person_count = (
            await session.execute(select(func.count(Person.id)))
        ).scalar_one()

        persons_created = 0
        persons_updated = 0
        new_person_ids: list[int] = []

        for face in new_clustered:
            label = face["cluster_label"]
            if label == -1:
                continue  # Noise face — no person assigned

            if label not in label_to_person_id:
                # Genuinely new cluster → create a Person.
                person = Person(name=f"人物 {existing_person_count + persons_created + 1}")
                session.add(person)
                await session.flush()  # get ID
                label_to_person_id[label] = person.id
                new_person_ids.append(person.id)
                persons_created += 1
            else:
                # Face joins an existing (or just-created) person.
                persons_updated += 1

        await session.commit()

    # ── 6. Save crop images (parallel, up to 4 at a time) ──────────────────────
    photo_id_to_path: dict[int, str] = {r.id: r.file_path for r in rows}

    def _save_crop_sync(face: ClusteredFace, person_id: int | None) -> str | None:
        src = photo_id_to_path.get(face["photo_id"])
        if not src or not person_id:
            return None
        crop_filename = f"person_{person_id}_p{face['photo_id']}.jpg"
        crop_dst = str(faces_dir / crop_filename)
        ok = save_face_crop(
            src,
            face["bbox_top"], face["bbox_right"],
            face["bbox_bottom"], face["bbox_left"],
            crop_dst,
        )
        return crop_dst if ok else None

    async def _bounded_save(face: ClusteredFace, person_id: int | None) -> str | None:
        return await loop.run_in_executor(_crop_executor, _save_crop_sync, face, person_id)

    crop_tasks = [
        _bounded_save(face, label_to_person_id.get(face["cluster_label"]))
        for face in new_clustered
    ]
    crop_paths: list[str | None] = await asyncio.gather(*crop_tasks)

    # ── 7. Persist FaceCrop rows ────────────────────────────────────────────────
    persons_created_final = 0

    async with AsyncSessionLocal() as session:
        for face, crop_path in zip(new_clustered, crop_paths):
            label = face["cluster_label"]
            person_id = label_to_person_id.get(label)

            fc = FaceCrop(
                photo_id=face["photo_id"],
                person_id=person_id,
                bbox_top=face["bbox_top"],
                bbox_right=face["bbox_right"],
                bbox_bottom=face["bbox_bottom"],
                bbox_left=face["bbox_left"],
                embedding=embedding_to_str(face["embedding"]),
                crop_path=crop_path,
            )
            session.add(fc)

        await session.commit()

    # ── 7. Backfill cover_path for ALL persons missing one (not just current run) ─
    #
    # Previous bug: only persons in label_to_person_id (created THIS run) were
    # covered. Persons from prior runs with cover_path=NULL never got one set.
    # Fix: query ALL Person rows where cover_path IS NULL and fill from FaceCrop.
    async with AsyncSessionLocal() as session:
        uncovered_persons = (
            await session.execute(
                select(Person).where(Person.cover_path.is_(None))
            )
        ).scalars().all()

        for person in uncovered_persons:
            first_crop = (
                await session.execute(
                    select(FaceCrop)
                    .where(FaceCrop.person_id == person.id)
                    .where(FaceCrop.crop_path.isnot(None))
                    .limit(1)
                )
            ).scalar_one_or_none()
            if first_crop:
                person.cover_path = first_crop.crop_path
                persons_created_final += 1

        await session.commit()

    # ── 7. Auto-prune persons below face_min_photos threshold ──────────────────
    from app.services.config_service import get_config as _get_config
    async with AsyncSessionLocal() as session:
        cfg = await _get_config(session)
        face_min = cfg.face_min_photos
    prune_result = await prune_small_persons(face_min)
    logger.info(
        "Auto-prune (min=%d): deleted %d persons, %d crops",
        face_min, prune_result["persons_deleted"], prune_result["crops_deleted"],
    )

    # Report only the new persons that survived pruning, so the stat matches
    # what actually shows up in the /persons list.
    persons_created_surviving = persons_created
    if new_person_ids:
        async with AsyncSessionLocal() as session:
            persons_created_surviving = (
                await session.execute(
                    select(func.count(Person.id)).where(Person.id.in_(new_person_ids))
                )
            ).scalar_one()

    return FaceRunResponse(
        photos_processed=len(rows),
        faces_detected=len(all_faces),
        persons_created=persons_created_surviving,
        persons_updated=persons_updated,
        message=(
            f"完成：{len(rows)} 张照片，检测到 {len(all_faces)} 张人脸，"
            f"新增 {persons_created_surviving} 位人物"
            + (f"（已自动清理 {prune_result['persons_deleted']} 个低频人物）" if prune_result["persons_deleted"] else "")
        ),
    )


# ── Query helpers ─────────────────────────────────────────────────────────────

async def list_persons(
    include_hidden: bool = False,
    page: int = 1,
    page_size: int = 10,
) -> dict:
    """
    Return paginated persons with photo counts and preview thumbnails.

    Uses a single LEFT JOIN + GROUP BY for aggregation, then a small inner
    query per person to fetch up to 4 preview photo thumbnail URLs.
    Falls back to the first available FaceCrop path when cover_path is NULL.
    """
    from app.models.photo import Photo as PhotoModel  # avoid circular import

    async with AsyncSessionLocal() as session:
        # Count total matching persons
        count_stmt = select(func.count(Person.id))
        if not include_hidden:
            count_stmt = count_stmt.where(Person.is_hidden.is_(False))
        total = (await session.execute(count_stmt)).scalar_one()

        # Subquery: distinct photo count per person
        photo_count_sq = (
            select(
                FaceCrop.person_id,
                func.count(FaceCrop.photo_id.distinct()).label("photo_count"),
            )
            .group_by(FaceCrop.person_id)
            .subquery()
        )

        # Subquery: first available crop_path per person (fallback cover)
        first_crop_sq = (
            select(
                FaceCrop.person_id,
                func.min(FaceCrop.id).label("min_crop_id"),
            )
            .where(FaceCrop.crop_path.is_not(None))
            .group_by(FaceCrop.person_id)
            .subquery()
        )
        crop_detail_sq = (
            select(FaceCrop.person_id, FaceCrop.crop_path)
            .join(first_crop_sq, FaceCrop.id == first_crop_sq.c.min_crop_id)
            .subquery()
        )

        stmt = (
            select(
                Person,
                func.coalesce(photo_count_sq.c.photo_count, 0).label("photo_count"),
                crop_detail_sq.c.crop_path.label("fallback_crop"),
            )
            .outerjoin(photo_count_sq, Person.id == photo_count_sq.c.person_id)
            .outerjoin(crop_detail_sq, Person.id == crop_detail_sq.c.person_id)
            .order_by(Person.name)
        )

        if not include_hidden:
            stmt = stmt.where(Person.is_hidden.is_(False))

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await session.execute(stmt)).all()

        result_items = []
        for p, photo_count, fallback_crop in rows:
            # Fetch up to 4 newest photo IDs for this person (for preview thumbnails)
            preview_stmt = (
                select(PhotoModel.id)
                .join(FaceCrop, FaceCrop.photo_id == PhotoModel.id)
                .where(FaceCrop.person_id == p.id, PhotoModel.is_deleted.is_(False))
                .distinct()
                .order_by(PhotoModel.taken_at.desc().nullslast(), PhotoModel.created_at.desc())
                .limit(4)
            )
            photo_ids = (await session.execute(preview_stmt)).scalars().all()
            preview_urls = [f"/api/v1/thumbnails/{pid}?size=256" for pid in photo_ids]

            result_items.append({
                "id": p.id,
                "name": p.name,
                "cover_path": p.cover_path or fallback_crop,
                "is_hidden": p.is_hidden,
                "is_locked": p.is_locked,
                "photo_count": photo_count,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
                "preview_photos": preview_urls,
            })

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": result_items,
        }


async def rebuild_covers() -> dict:
    """
    One-time backfill: for every Person with cover_path=NULL that has at least
    one FaceCrop with a saved crop image, set cover_path to that crop.

    Safe to call multiple times (idempotent — only touches NULL rows).
    Returns counts of persons updated and persons still missing a cover.
    """
    updated = 0
    still_missing = 0

    async with AsyncSessionLocal() as session:
        uncovered = (
            await session.execute(
                select(Person).where(Person.cover_path.is_(None))
            )
        ).scalars().all()

        for person in uncovered:
            first_crop = (
                await session.execute(
                    select(FaceCrop)
                    .where(FaceCrop.person_id == person.id)
                    .where(FaceCrop.crop_path.isnot(None))
                    .limit(1)
                )
            ).scalar_one_or_none()
            if first_crop:
                person.cover_path = first_crop.crop_path
                updated += 1
            else:
                still_missing += 1

        await session.commit()

    logger.info("rebuild_covers: updated=%d still_missing=%d", updated, still_missing)
    return {"updated": updated, "still_missing": still_missing}


async def get_person_photos(person_id: int, page: int = 1, page_size: int = 80) -> dict:
    """Return paginated photos that contain a given person."""
    async with AsyncSessionLocal() as session:
        distinct_photo_ids = (
            select(FaceCrop.photo_id)
            .where(FaceCrop.person_id == person_id)
            .distinct()
            .subquery()
        )

        total = (
            await session.execute(select(func.count()).select_from(distinct_photo_ids))
        ).scalar_one()

        stmt = (
            select(Photo)
            .where(Photo.id.in_(select(FaceCrop.photo_id).where(FaceCrop.person_id == person_id).distinct()))
            .where(Photo.is_deleted.is_(False))
            .order_by(Photo.taken_at.desc().nullslast(), Photo.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        photos = (await session.execute(stmt)).scalars().all()

        return {"total": total, "page": page, "page_size": page_size, "items": photos}


async def get_person_by_id(person_id: int) -> dict | None:
    """Return a single person dict (same shape as list_persons items) or None."""
    async with AsyncSessionLocal() as session:
        from app.models.photo import Photo as PhotoModel  # avoid circular import

        person = await session.get(Person, person_id)
        if not person:
            return None

        photo_count = (
            await session.execute(
                select(func.count(FaceCrop.photo_id.distinct()))
                .where(FaceCrop.person_id == person_id)
            )
        ).scalar_one()

        cover_path = person.cover_path
        if not cover_path:
            row = (
                await session.execute(
                    select(FaceCrop.crop_path)
                    .where(FaceCrop.person_id == person_id)
                    .where(FaceCrop.crop_path.isnot(None))
                    .limit(1)
                )
            ).scalar_one_or_none()
            cover_path = row

        photo_ids = (
            await session.execute(
                select(PhotoModel.id)
                .join(FaceCrop, FaceCrop.photo_id == PhotoModel.id)
                .where(FaceCrop.person_id == person_id, PhotoModel.is_deleted.is_(False))
                .order_by(PhotoModel.taken_at.desc().nullslast(), PhotoModel.created_at.desc())
                .limit(4)
            )
        ).scalars().all()

        return {
            "id": person.id,
            "name": person.name,
            "cover_path": cover_path,
            "is_hidden": person.is_hidden,
            "is_locked": person.is_locked,
            "photo_count": photo_count,
            "created_at": person.created_at,
            "updated_at": person.updated_at,
            "preview_photos": [f"/api/v1/thumbnails/{pid}?size=256" for pid in photo_ids],
        }


async def prune_small_persons(min_photos: int = 2) -> dict:
    """
    Delete Person rows (+ their FaceCrop rows) whose photo count < min_photos.
    Locked persons are always preserved.
    """
    async with AsyncSessionLocal() as session:
        # Find person IDs with too few photos, excluding locked ones
        subq = (
            select(FaceCrop.person_id, func.count(FaceCrop.id).label("cnt"))
            .where(FaceCrop.person_id.is_not(None))
            .group_by(FaceCrop.person_id)
            .subquery()
        )
        result = await session.execute(
            select(Person.id)
            .join(subq, Person.id == subq.c.person_id, isouter=True)
            .where(
                Person.is_locked.is_(False),
                (subq.c.cnt < min_photos) | (subq.c.cnt.is_(None)),
            )
        )
        ids_to_delete = [row[0] for row in result.all()]

        if not ids_to_delete:
            return {"persons_deleted": 0, "crops_deleted": 0}

        crop_result = await session.execute(
            delete(FaceCrop).where(FaceCrop.person_id.in_(ids_to_delete))
        )
        person_result = await session.execute(
            delete(Person).where(Person.id.in_(ids_to_delete))
        )
        await session.commit()

    return {
        "persons_deleted": person_result.rowcount,
        "crops_deleted": crop_result.rowcount,
    }


async def reset_face_data() -> dict:
    """Delete ALL face recognition data (FaceCrop + Person rows) and clear face_analyzed_at checkpoints."""
    async with AsyncSessionLocal() as session:
        crop_result = await session.execute(delete(FaceCrop))
        person_result = await session.execute(delete(Person))
        # Clear checkpoints so next /run re-processes all photos from scratch
        await session.execute(
            Photo.__table__.update().values(face_analyzed_at=None)
        )
        await session.commit()
    return {
        "crops_deleted": crop_result.rowcount,
        "persons_deleted": person_result.rowcount,
    }


async def rename_person(person_id: int, name: str) -> Person | None:
    """Rename a person by ID."""
    async with AsyncSessionLocal() as session:
        person = await session.get(Person, person_id)
        if not person:
            return None
        person.name = name.strip()
        await session.commit()
        await session.refresh(person)
        return person


async def merge_persons(source_id: int, target_id: int) -> bool:
    """Reassign all face crops from source → target, then delete source."""
    async with AsyncSessionLocal() as session:
        source = await session.get(Person, source_id)
        target = await session.get(Person, target_id)
        if not source or not target:
            return False

        await session.execute(
            FaceCrop.__table__.update()
            .where(FaceCrop.person_id == source_id)
            .values(person_id=target_id)
        )
        await session.delete(source)
        await session.commit()
        return True


async def hide_person(person_id: int, hidden: bool = True) -> Person | None:
    """Hide or unhide a person."""
    async with AsyncSessionLocal() as session:
        person = await session.get(Person, person_id)
        if not person:
            return None
        person.is_hidden = hidden
        await session.commit()
        await session.refresh(person)
        return person


async def lock_person(person_id: int, locked: bool = True) -> Person | None:
    """Lock or unlock a person (locked persons cannot be deleted)."""
    async with AsyncSessionLocal() as session:
        person = await session.get(Person, person_id)
        if not person:
            return None
        person.is_locked = locked
        await session.commit()
        await session.refresh(person)
        return person


async def delete_person(person_id: int) -> bool:
    """
    Delete a person and all their FaceCrop records.
    The underlying photos are NOT deleted — only the face recognition data.
    Raises ValueError if the person is locked.
    """
    async with AsyncSessionLocal() as session:
        person = await session.get(Person, person_id)
        if not person:
            return False
        if person.is_locked:
            raise ValueError(f"Person {person_id} is locked and cannot be deleted")
        await session.delete(person)   # CASCADE deletes FaceCrop rows
        await session.commit()
    return True
