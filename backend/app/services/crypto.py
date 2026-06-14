"""
crypto.py — Fernet symmetric encryption for sensitive fields (API keys).

Key file: /app/data/secret.key  (same Docker volume as the database)
Auto-generated on first run; survives container restarts.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

_KEY_PATH = Path("/app/data/secrets/secret.key")


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """Load or generate the Fernet key (cached for the process lifetime)."""
    if _KEY_PATH.exists():
        key = _KEY_PATH.read_bytes().strip()
    else:
        key = Fernet.generate_key()
        _KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _KEY_PATH.write_bytes(key)
        logger.info("crypto: generated new Fernet key at %s", _KEY_PATH)
    return Fernet(key)


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string → URL-safe base64 ciphertext string."""
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a ciphertext string → plaintext. Returns '' on failure."""
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except Exception:
        # Expected when secret.key changed between deployments; caller handles empty return
        logger.debug("crypto: decryption failed (key mismatch or invalid ciphertext)")
        return ""


def mask_key(ciphertext: str) -> str:
    """
    Return a display-safe masked version of the key for frontend responses.
    Never decrypts — works purely on the encrypted string length heuristic.
    Decrypts only enough to get prefix/suffix chars, then re-masks.

    Format: first 4 chars + ****....**** + last 4 chars of the plaintext.
    Falls back to generic mask if decryption fails.
    """
    if not ciphertext:
        return ""
    plain = decrypt(ciphertext)
    if not plain:
        return "****"
    if len(plain) <= 8:
        return "*" * len(plain)
    return f"{plain[:4]}{'*' * (len(plain) - 8)}{plain[-4:]}"
