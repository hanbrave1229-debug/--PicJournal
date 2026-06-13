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

# Single-thread executor: face detection is CPU-bound; one photo at a time
# prevents all NAS cores from being saturated simultaneously.
_face_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="face")


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
            # Skip photos that already have face crops
            existing_photo_ids = (
                await session.execute(select(FaceCrop.photo_id).distinct())
            ).scalars().all()
            if existing_photo_ids:
                stmt = stmt.where(Photo.id.not_in(existing_photo_ids))

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

    existing_faces: list[DetectedFace] = [
        DetectedFace(
            photo_id=c.photo_id,
            bbox_top=c.bbox_top,
            bbox_right=c.bbox_right,
            bbox_bottom=c.bbox_bottom,
            bbox_left=c.bbox_left,
            embedding=[float(v) for v in c.embedding.split(",")],
        )
        for c in existing_crops
        # Only include embeddings with matching dimension (skip legacy 128-dim from face_recognition)
        if c.embedding and len(c.embedding.split(",")) == EMBEDDING_DIM
    ]

    combined_faces = existing_faces + all_faces

    # ── 4. Re-cluster all embeddings ──────────────────────────────────────────
    clustered: list[ClusteredFace] = cluster_faces(combined_faces)

    # Only process the NEW portion (tail of combined list)
    new_clustered = clustered[len(existing_faces):]

    # ── 5. Map cluster labels → Person rows ────────────────────────────────────
    async with AsyncSessionLocal() as session:
        # Load existing persons
        existing_persons = (
            await session.execute(select(Person))
        ).scalars().all()

        # cluster_label → person_id mapping
        # We use DBSCAN labels starting from 0; shift by max existing person id
        max_existing_label = len(existing_persons)
        label_to_person_id: dict[int, int] = {}
        persons_created = 0
        persons_updated = 0

        for face in new_clustered:
            label = face["cluster_label"]
            if label == -1:
                continue  # Noise face — no person assigned

            if label not in label_to_person_id:
                # Create new Person
                person = Person(name=f"人物 {max_existing_label + persons_created + 1}")
                session.add(person)
                await session.flush()  # get ID
                label_to_person_id[label] = person.id
                persons_created += 1
            else:
                persons_updated += 1

        await session.commit()

    # ── 6. Persist FaceCrop rows + save crop images ────────────────────────────
    photo_id_to_path: dict[int, str] = {r.id: r.file_path for r in rows}
    persons_created_final = 0

    async with AsyncSessionLocal() as session:
        for face in new_clustered:
            label = face["cluster_label"]
            person_id = label_to_person_id.get(label)

            crop_path: str | None = None
            # Save face crop image
            src = photo_id_to_path.get(face["photo_id"])
            if src and person_id:
                crop_filename = f"person_{person_id}_p{face['photo_id']}.jpg"
                crop_dst = str(faces_dir / crop_filename)
                ok = await loop.run_in_executor(
                    None,
                    save_face_crop,
                    src,
                    face["bbox_top"],
                    face["bbox_right"],
                    face["bbox_bottom"],
                    face["bbox_left"],
                    crop_dst,
                )
                if ok:
                    crop_path = crop_dst

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

    return FaceRunResponse(
        photos_processed=len(rows),
        faces_detected=len(all_faces),
        persons_created=persons_created,
        persons_updated=persons_updated,
        message=f"完成：{len(rows)} 张照片，检测到 {len(all_faces)} 张人脸，识别 {persons_created} 位人物",
    )


# ── Query helpers ─────────────────────────────────────────────────────────────

async def list_persons(include_hidden: bool = False) -> list[dict]:
    """
    Return all persons with photo counts.

    Uses a single LEFT JOIN + GROUP BY instead of N+1 individual count queries,
    which is critical when there are hundreds of persons.
    """
    async with AsyncSessionLocal() as session:
        # Subquery: distinct photo count per person
        photo_count_sq = (
            select(
                FaceCrop.person_id,
                func.count(FaceCrop.photo_id.distinct()).label("photo_count"),
            )
            .group_by(FaceCrop.person_id)
            .subquery()
        )

        stmt = (
            select(
                Person,
                func.coalesce(photo_count_sq.c.photo_count, 0).label("photo_count"),
            )
            .outerjoin(photo_count_sq, Person.id == photo_count_sq.c.person_id)
            .order_by(Person.name)
        )

        if not include_hidden:
            stmt = stmt.where(Person.is_hidden.is_(False))

        rows = (await session.execute(stmt)).all()

        return [
            {
                "id": p.id,
                "name": p.name,
                "cover_path": p.cover_path,
                "is_hidden": p.is_hidden,
                "is_locked": p.is_locked,
                "photo_count": photo_count,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
            }
            for p, photo_count in rows
        ]


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
        # Distinct photo IDs for this person
        subq = (
            select(FaceCrop.photo_id)
            .where(FaceCrop.person_id == person_id)
            .distinct()
            .subquery()
        )

        total_result = await session.execute(
            select(subq.c.photo_id)
        )
        total = len(total_result.all())

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
