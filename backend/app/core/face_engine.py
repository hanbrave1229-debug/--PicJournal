"""
Face detection, embedding, and DBSCAN clustering engine.

Dependencies:
    face_recognition  — dlib-based HOG/CNN detector + 128-dim ResNet embeddings
    scikit-learn      — DBSCAN for unsupervised face clustering
    numpy             — array ops
    Pillow            — image crop & save
"""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import TypedDict

import numpy as np

logger = logging.getLogger(__name__)

# ── Optional heavy imports (graceful degrade if not installed) ────────────────
try:
    import face_recognition  # type: ignore
    FACE_RECOGNITION_AVAILABLE = True
except BaseException:
    # face_recognition calls quit() (SystemExit) when face_recognition_models is missing.
    # Catch BaseException (not just ImportError) to prevent crashing the backend process.
    face_recognition = None  # type: ignore
    FACE_RECOGNITION_AVAILABLE = False
    logger.warning("face_recognition unavailable (dlib or face_recognition_models missing)")

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


# ── Types ─────────────────────────────────────────────────────────────────────
class DetectedFace(TypedDict):
    """One detected face within a single photo."""
    photo_id: int
    bbox_top: int
    bbox_right: int
    bbox_bottom: int
    bbox_left: int
    embedding: list[float]  # 128-dim


class ClusteredFace(DetectedFace):
    """DetectedFace enriched with a cluster label (−1 = noise/unassigned)."""
    cluster_label: int


# ── Detection ─────────────────────────────────────────────────────────────────
def detect_faces_in_image(photo_id: int, image_path: str) -> list[DetectedFace]:
    """
    Detect all faces in a single image and return their bounding boxes + embeddings.

    Args:
        photo_id: DB primary key of the Photo.
        image_path: Absolute filesystem path to the image file.

    Returns:
        List of DetectedFace dicts; empty if no faces found or library unavailable.
    """
    if not FACE_RECOGNITION_AVAILABLE:
        return []

    try:
        img = face_recognition.load_image_file(image_path)
    except Exception as exc:
        logger.warning("Cannot load image %s: %s", image_path, exc)
        return []

    # Use HOG model (fast); switch to "cnn" for GPU-accelerated accuracy
    locations = face_recognition.face_locations(img, model="hog")
    if not locations:
        return []

    try:
        encodings = face_recognition.face_encodings(img, known_face_locations=locations)
    except Exception as exc:
        logger.warning("Encoding failed for %s: %s", image_path, exc)
        return []

    results: list[DetectedFace] = []
    for (top, right, bottom, left), encoding in zip(locations, encodings):
        results.append(
            DetectedFace(
                photo_id=photo_id,
                bbox_top=top,
                bbox_right=right,
                bbox_bottom=bottom,
                bbox_left=left,
                embedding=encoding.tolist(),
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
    Assign each face to a cluster (= person) using DBSCAN on L2 distance
    of 128-dim embeddings.

    Args:
        faces:       All detected faces across the entire library.
        eps:         DBSCAN neighbourhood radius. 0.5 works well for face_recognition
                     embeddings (Euclidean). Lower = stricter separation.
        min_samples: Minimum faces per cluster to be considered a core point.
                     Set to 1 so single-occurrence people are still tracked.

    Returns:
        Same list with `cluster_label` added. Label −1 = noise (far outliers).
    """
    if not SKLEARN_AVAILABLE or not faces:
        return [ClusteredFace(**f, cluster_label=-1) for f in faces]  # type: ignore[misc]

    embeddings = np.array([f["embedding"] for f in faces], dtype=np.float32)

    db = DBSCAN(eps=eps, min_samples=min_samples, metric="euclidean", n_jobs=-1)
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

    Args:
        image_path:    Source image path.
        output_path:   Destination JPEG path (parent dir must exist).
        padding_ratio: Fraction of bbox size to add as padding on each side.

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

    # Resize to 256×256 square (cover crop)
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
    """Serialize 128-dim float list to comma-separated string for DB storage."""
    return ",".join(f"{v:.6f}" for v in embedding)


def str_to_embedding(s: str) -> np.ndarray:
    """Deserialize embedding string back to numpy float32 array."""
    return np.array([float(v) for v in s.split(",")], dtype=np.float32)
