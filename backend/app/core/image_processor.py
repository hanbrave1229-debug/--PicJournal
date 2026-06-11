"""
ImageProcessor — hash computation for individual image files.

Two hash types:
  MD5   — exact binary fingerprint (block-read, memory-safe for RAW files > 100 MB).
  pHash — perceptual hash via imagehash; tolerant of re-compression, minor crops,
          format conversion.  Hamming distance ≤ threshold → visually similar.

All methods are **synchronous** and CPU-bound.
Call them via ProcessPoolExecutor (scanner already uses one) or
asyncio.get_event_loop().run_in_executor() for one-offs.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import NamedTuple

import imagehash
from PIL import Image


# ── Result container ──────────────────────────────────────────────────────────

class HashResult(NamedTuple):
    photo_id: int
    file_path: str
    md5: str | None
    phash: str | None


# ── Core class ────────────────────────────────────────────────────────────────

class ImageProcessor:
    """Stateless helper — instantiate once and reuse across the process pool."""

    # Block size for streaming MD5 (8 MiB — safe for 4K RAW files)
    _MD5_BLOCK = 8 * 1024 * 1024

    # ── MD5 ───────────────────────────────────────────────────────────────────

    @classmethod
    def compute_md5(cls, file_path: str | Path) -> str | None:
        """
        Compute the MD5 digest of a file using block-by-block streaming.

        Never loads the whole file into memory — safe for files of any size.
        Returns the hex digest string, or None if the file is unreadable.
        """
        try:
            h = hashlib.md5()
            with open(file_path, "rb") as fh:
                while chunk := fh.read(cls._MD5_BLOCK):
                    h.update(chunk)
            return h.hexdigest()
        except OSError:
            return None

    # ── pHash ─────────────────────────────────────────────────────────────────

    @classmethod
    def compute_phash(cls, file_path: str | Path) -> str | None:
        """
        Compute the perceptual hash (DCT-based pHash) of an image.

        The hash is stored as a 16-char hex string (64-bit).
        Returns None if the file cannot be opened as an image.
        """
        try:
            with Image.open(file_path) as img:
                # Convert to RGB — imagehash handles greyscale internally but
                # palette-mode images can cause issues.
                if img.mode not in ("RGB", "L", "RGBA"):
                    img = img.convert("RGB")
                return str(imagehash.phash(img))
        except Exception:
            return None

    # ── Hamming distance ──────────────────────────────────────────────────────

    @staticmethod
    def phash_distance(hash_a: str, hash_b: str) -> int | None:
        """
        Compute the Hamming distance between two pHash hex strings.

        Lower distance = more visually similar.
          0        → identical or near-identical
          1–10     → very similar (minor compression / crop)
          11–20    → somewhat similar
          > 20     → likely different subjects

        Returns None if either hash is invalid.
        """
        try:
            return imagehash.hex_to_hash(hash_a) - imagehash.hex_to_hash(hash_b)
        except Exception:
            return None

    # ── Combined ──────────────────────────────────────────────────────────────

    @classmethod
    def compute_all(cls, photo_id: int, file_path: str) -> HashResult:
        """
        Compute both MD5 and pHash for a single file.
        Intended to run inside a ProcessPoolExecutor worker.
        """
        return HashResult(
            photo_id=photo_id,
            file_path=file_path,
            md5=cls.compute_md5(file_path),
            phash=cls.compute_phash(file_path),
        )


# ── Module-level convenience function (picklable for multiprocessing) ─────────

def compute_hashes(photo_id: int, file_path: str) -> HashResult:
    """Top-level wrapper — required for ProcessPoolExecutor (lambdas aren't picklable)."""
    return ImageProcessor.compute_all(photo_id, file_path)
