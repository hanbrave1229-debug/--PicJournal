"""
Image quality scorer — two objective metrics computed via OpenCV.

Metric 1 — Sharpness (Laplacian variance)
  Convert to greyscale → apply Laplacian operator → compute pixel variance.
  High variance  = well-defined edges = sharp image.
  Low variance   = smooth, blurry, or out-of-focus image.

  Empirical thresholds (calibrated on consumer photos):
    < 80    → blurry / hand-shake / defocus
    80–300  → acceptable / slightly soft
    > 300   → sharp

  Note: the absolute value depends on resolution.  For very high-res images
  (e.g. 48 MP phone shots) the score is naturally higher.  Caller may want to
  normalise by (width × height) for cross-camera comparison.

Metric 2 — Exposure score (histogram mean normalised to [0, 1])
  Convert to greyscale → compute 256-bin histogram →
  compute the weighted mean pixel intensity (0 = black, 255 = white).
  Normalise to [0, 1].

  Interpretation:
    < 0.05  → severe underexposure (almost completely black)
    0.05–0.95 → normal range
    > 0.95  → severe overexposure (blown highlights / white)

All functions are **synchronous and CPU-bound**.
Use ProcessPoolExecutor / run_in_executor when calling from async code.
"""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple


# ── Result container ──────────────────────────────────────────────────────────

class ScoreResult(NamedTuple):
    photo_id: int
    file_path: str
    sharpness_score: float | None   # Laplacian variance
    exposure_score: float | None    # 0.0–1.0 normalised mean intensity


# ── Low-level scorers ─────────────────────────────────────────────────────────

def _compute_sharpness(grey_img) -> float:
    """
    Compute the Laplacian variance of a greyscale OpenCV image.

    Uses a 3×3 Laplacian kernel.  Returns the variance of the resulting
    gradient image — a single float ≥ 0.
    """
    import cv2
    import numpy as np

    laplacian = cv2.Laplacian(grey_img, cv2.CV_64F)
    return float(np.var(laplacian))


def _compute_exposure(grey_img) -> float:
    """
    Compute the normalised mean pixel intensity of a greyscale image.

    Returns a float in [0.0, 1.0]:
      0.0  → completely black
      1.0  → completely white
    """
    import cv2
    import numpy as np

    hist = cv2.calcHist([grey_img], [0], None, [256], [0, 256])
    hist = hist.flatten()
    total_pixels = grey_img.shape[0] * grey_img.shape[1]

    if total_pixels == 0:
        return 0.5

    # Weighted mean intensity (0–255), normalised to [0, 1]
    bins = np.arange(256, dtype=np.float64)
    mean_intensity = float(np.dot(hist, bins) / total_pixels)
    return round(mean_intensity / 255.0, 4)


# ── Top-level worker (picklable for multiprocessing) ──────────────────────────

def score_image(photo_id: int, file_path: str) -> ScoreResult:
    """
    Compute sharpness and exposure scores for a single image file.

    This function runs in a child process — it must be picklable
    (no lambdas, no closures over non-picklable objects).

    Gracefully returns None scores on any error (corrupt file, unsupported
    format, memory error on very large RAW files, etc.).
    """
    try:
        import cv2

        path = Path(file_path)
        if not path.exists():
            return ScoreResult(photo_id, file_path, None, None)

        # cv2.IMREAD_GRAYSCALE avoids decoding colour channels we don't need,
        # saving ~3× memory and time for large images.
        img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)

        if img is None:
            # OpenCV cannot decode this format (e.g. HEIC without plugin).
            # Fall back to Pillow → numpy for HEIC/AVIF/WebP support.
            img = _pillow_to_grey_array(file_path)

        if img is None:
            return ScoreResult(photo_id, file_path, None, None)

        # Downsample very large images before computing the Laplacian to keep
        # processing time bounded (< 200 ms per image on a modern CPU).
        # Target: at most 2 MP for scoring purposes.
        h, w = img.shape[:2]
        max_px = 2_000_000
        if h * w > max_px:
            scale = (max_px / (h * w)) ** 0.5
            new_w, new_h = int(w * scale), int(h * scale)
            import cv2 as _cv2
            img = _cv2.resize(img, (new_w, new_h), interpolation=_cv2.INTER_AREA)

        sharpness = _compute_sharpness(img)
        exposure = _compute_exposure(img)

        return ScoreResult(photo_id, file_path, sharpness, exposure)

    except Exception:
        return ScoreResult(photo_id, file_path, None, None)


def _pillow_to_grey_array(file_path: str):
    """
    Fallback: open with Pillow and convert to a numpy greyscale array
    compatible with OpenCV.  Returns None on failure.
    """
    try:
        import numpy as np
        from PIL import Image, ImageOps

        with Image.open(file_path) as img:
            img = ImageOps.exif_transpose(img)
            grey = img.convert("L")
            return np.array(grey, dtype=np.uint8)
    except Exception:
        return None


# ── Convenience class (optional — useful in tests) ────────────────────────────

class ImageScorer:
    """
    Thin wrapper around score_image for use in synchronous contexts.
    Prefer the top-level score_image() function in async/multiprocess code.
    """

    @staticmethod
    def score(photo_id: int, file_path: str) -> ScoreResult:
        return score_image(photo_id, file_path)

    @staticmethod
    def is_blurry(sharpness: float | None, threshold: float = 80.0) -> bool:
        """Return True if the sharpness score is below the blur threshold."""
        return sharpness is not None and sharpness < threshold

    @staticmethod
    def is_underexposed(exposure: float | None, threshold: float = 0.05) -> bool:
        return exposure is not None and exposure < threshold

    @staticmethod
    def is_overexposed(exposure: float | None, threshold: float = 0.95) -> bool:
        return exposure is not None and exposure > threshold
