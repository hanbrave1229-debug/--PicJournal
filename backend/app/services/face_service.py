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
import logging
from pathlib import Path

from sqlalchemy import delete, select

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


# ── Public API ────────────────────────────────────────────────────────────────

async def get_status() -> dict:
    return {"running": _is_running, "last_run_result": _last_result}


async def run_face_analysis(force: bool = False) -> FaceRunResponse:
    """
    Run the full face detection + clustering pipeline.

    Args:
        force: If True, re-detect faces for photos that already have FaceCrops.
    """
    global _is_running, _last_result

    if not FACE_RECOGNITION_AVAILABLE:
        raise RuntimeError(
            "insightface 或 onnxruntime 未正确安装。"
            "请拉取最新 Docker 镜像（docker compose pull && docker compose up -d）。"
        )
    if not SKLEARN_AVAILABLE:
        raise RuntimeError("scikit-learn 未安装，无法执行人脸聚类。")

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

    for row in rows:
        faces = await loop.run_in_executor(
            None, detect_faces_in_image, row.id, row.file_path
        )
        all_faces.extend(faces)

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

    # ── 7. Update Person.cover_path for newly created persons ─────────────────
    async with AsyncSessionLocal() as session:
        for label, pid in label_to_person_id.items():
            first_crop = (
                await session.execute(
                    select(FaceCrop)
                    .where(FaceCrop.person_id == pid)
                    .where(FaceCrop.crop_path.isnot(None))
                    .limit(1)
                )
            ).scalar_one_or_none()

            if first_crop:
                person = await session.get(Person, pid)
                if person and not person.cover_path:
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
    """Return all persons with photo counts."""
    async with AsyncSessionLocal() as session:
        persons = (
            await session.execute(
                select(Person)
                .where(Person.is_hidden.is_(include_hidden) if not include_hidden else True)
                .order_by(Person.name)
            )
        ).scalars().all()

        result = []
        for p in persons:
            # Count distinct photos for this person
            count_result = await session.execute(
                select(FaceCrop.photo_id)
                .where(FaceCrop.person_id == p.id)
                .distinct()
            )
            photo_count = len(count_result.all())

            result.append({
                "id": p.id,
                "name": p.name,
                "cover_path": p.cover_path,
                "is_hidden": p.is_hidden,
                "photo_count": photo_count,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
            })

        return result


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
