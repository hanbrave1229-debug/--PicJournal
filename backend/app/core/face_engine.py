"""
Face detection, embedding, and DBSCAN clustering engine.

Backend: InsightFace (buffalo_sc) + ONNX Runtime
  — no dlib, no cmake, pure pip install
  — 512-dim ArcFace embeddings (L2-normalized)
  — DBSCAN clustering on cosine distance
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TypedDict

import numpy as np

logger = logging.getLogger(__name__)

# Limit ONNX Runtime / OpenMP thread count so face recognition doesn't saturate
# all NAS CPU cores and block other requests. Set before any ONNX import.
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

# ── Optional heavy imports ────────────────────────────────────────────────────
try:
    import cv2  # type: ignore
    _CV2_AVAILABLE = True
except ImportError:
    cv2 = None  # type: ignore
    _CV2_AVAILABLE = False
    logger.warning("opencv-python not found")

try:
    from insightface.app import FaceAnalysis  # type: ignore
    FACE_RECOGNITION_AVAILABLE = True  # kept for backward-compat with face_service.py
except Exception:
    FaceAnalysis = None  # type: ignore
    FACE_RECOGNITION_AVAILABLE = False
    logger.warning("insightface unavailable — face recognition disabled")

try:
    from sklearn.cluster import DBSCAN  # type: ignore
    SKLEARN_AVAILABLE = True
except ImportError:
    DBSCAN = None  # type: ignore
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not installed — face clustering unavailable")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    Image = None  # type: ignore
    PIL_AVAILABLE = False

# ArcFace embedding dimension (InsightFace buffalo_sc)
EMBEDDING_DIM = 512

# ── InsightFace singleton (lazy init) ─────────────────────────────────────────
_face_app: "FaceAnalysis | None" = None


def _get_face_app() -> "FaceAnalysis | None":
    """Lazily initialize InsightFace app. Thread-safe for single-process async."""
    global _face_app
    if _face_app is None and FACE_RECOGNITION_AVAILABLE:
        try:
            import onnxruntime as ort  # type: ignore
            # Limit ONNX Runtime threads per session to avoid CPU saturation on NAS
            sess_opts = ort.SessionOptions()
            sess_opts.inter_op_num_threads = 1
            sess_opts.intra_op_num_threads = 2

            _face_app = FaceAnalysis(
                name="buffalo_sc",
                providers=["CPUExecutionProvider"],
                session_options=sess_opts,
            )
            _face_app.prepare(ctx_id=0, det_size=(640, 640))
            logger.info("InsightFace buffalo_sc loaded (threads capped at 2)")
        except Exception as exc:
            logger.error("InsightFace init failed: %s", exc)
    return _face_app


# ── Types ─────────────────────────────────────────────────────────────────────
class DetectedFace(TypedDict):
    """One detected face within a single photo."""
    photo_id: int
    bbox_top: int
    bbox_right: int
    bbox_bottom: int
    bbox_left: int
    embedding: list[float]  # 512-dim ArcFace


class ClusteredFace(DetectedFace):
    """DetectedFace enriched with a cluster label (−1 = noise/unassigned)."""
    cluster_label: int


# ── Detection ─────────────────────────────────────────────────────────────────
def detect_faces_in_image(photo_id: int, image_path: str) -> list[DetectedFace]:
    """
    Detect all faces in a single image and return bounding boxes + ArcFace embeddings.

    Args:
        photo_id:   DB primary key of the Photo.
        image_path: Absolute filesystem path to the image file.

    Returns:
        List of DetectedFace dicts; empty if no faces found or library unavailable.
    """
    if not FACE_RECOGNITION_AVAILABLE or not _CV2_AVAILABLE:
        return []

    app = _get_face_app()
    if app is None:
        return []

    try:
        img = cv2.imread(image_path)
        if img is None:
            logger.warning("Cannot read image: %s", image_path)
            return []
        faces = app.get(img)
    except Exception as exc:
        logger.warning("Face detection failed for %s: %s", image_path, exc)
        return []

    results: list[DetectedFace] = []
    for face in faces:
        if face.det_score < 0.5:
            continue  # Low-confidence detection
        if face.embedding is None:
            continue

        x1, y1, x2, y2 = face.bbox.astype(int)
        results.append(
            DetectedFace(
                photo_id=photo_id,
                bbox_top=int(y1),
                bbox_right=int(x2),
                bbox_bottom=int(y2),
                bbox_left=int(x1),
                embedding=face.embedding.tolist(),  # 512-dim L2-normalized
            )
        )
    return results


# ── Clustering ────────────────────────────────────────────────────────────────
def cluster_faces(
    faces: list[DetectedFace],
    eps: float = 0.5,
    min_samples: int = 1,
) -> list[ClusteredFace]:
    """
    Assign each face to a cluster (= person) using DBSCAN on cosine distance
    of 512-dim ArcFace embeddings (L2-normalized unit vectors).

    Args:
        faces:       All detected faces across the entire library.
        eps:         DBSCAN cosine-distance threshold. 0.5 ≈ cos_sim > 0.5,
                     which works well for InsightFace buffalo_sc.
        min_samples: Minimum faces per cluster. 1 so single-photo persons are kept.

    Returns:
        Same list with `cluster_label` added. Label −1 = noise (outlier).
    """
    if not SKLEARN_AVAILABLE or not faces:
        return [ClusteredFace(**f, cluster_label=-1) for f in faces]  # type: ignore[misc]

    embeddings = np.array([f["embedding"] for f in faces], dtype=np.float32)

    db = DBSCAN(eps=eps, min_samples=min_samples, metric="cosine", n_jobs=-1)
    labels: np.ndarray = db.fit_predict(embeddings)

    return [
        ClusteredFace(**f, cluster_label=int(label))  # type: ignore[misc]
        for f, label in zip(faces, labels)
    ]


# ── Face crop saver ───────────────────────────────────────────────────────────
def save_face_crop(
    image_path: str,
    bbox_top: int,
    bbox_right: int,
    bbox_bottom: int,
    bbox_left: int,
    output_path: str,
    padding_ratio: float = 0.3,
) -> bool:
    """
    Crop the face region (with padding) from an image and save as JPEG.

    Returns:
        True if saved successfully, False otherwise.
    """
    if not PIL_AVAILABLE:
        return False

    try:
        img = Image.open(image_path).convert("RGB")
    except Exception as exc:
        logger.warning("Cannot open %s for crop: %s", image_path, exc)
        return False

    w, h = img.size
    face_h = bbox_bottom - bbox_top
    face_w = bbox_right - bbox_left
    pad_v = int(face_h * padding_ratio)
    pad_h = int(face_w * padding_ratio)

    top    = max(0, bbox_top    - pad_v)
    bottom = min(h, bbox_bottom + pad_v)
    left   = max(0, bbox_left   - pad_h)
    right  = min(w, bbox_right  + pad_h)

    crop = img.crop((left, top, right, bottom))
    crop = crop.resize((256, 256), Image.LANCZOS)

    try:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        crop.save(output_path, "JPEG", quality=85)
        return True
    except Exception as exc:
        logger.warning("Cannot save crop to %s: %s", output_path, exc)
        return False


# ── Embedding serialization ───────────────────────────────────────────────────
def embedding_to_str(embedding: list[float]) -> str:
    """Serialize 512-dim float list to comma-separated string for DB storage."""
    return ",".join(f"{v:.6f}" for v in embedding)


def str_to_embedding(s: str) -> np.ndarray:
    """Deserialize embedding string back to numpy float32 array."""
    return np.array([float(v) for v in s.split(",")], dtype=np.float32)
