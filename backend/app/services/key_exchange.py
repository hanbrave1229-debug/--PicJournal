"""
key_exchange.py — Ephemeral RSA-OAEP key pair for encrypting API keys in transit.

The private key lives only in memory and is regenerated on every process start.
Frontend encrypts the api_key with the public key before sending; the backend
decrypts it here, then re-encrypts with Fernet for at-rest storage.

This prevents the raw api_key from being logged by proxies or visible in
plaintext request bodies (even though on a local HTTP network it is still
technically sniffable — HTTPS is the proper long-term solution).
"""
from __future__ import annotations

import base64

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

# ── Generate ephemeral key pair on import ─────────────────────────────────────

_private_key: rsa.RSAPrivateKey = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)
_public_key: rsa.RSAPublicKey = _private_key.public_key()


def get_public_key_spki_b64() -> str:
    """Return the DER-encoded SubjectPublicKeyInfo (SPKI) as base64.
    This format is accepted directly by the WebCrypto SubtleCrypto API.
    """
    der = _public_key.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return base64.b64encode(der).decode()


def rsa_decrypt(ciphertext_b64: str) -> str:
    """Decrypt a base64-encoded RSA-OAEP ciphertext produced by the frontend."""
    ciphertext = base64.b64decode(ciphertext_b64)
    plaintext = _private_key.decrypt(
        ciphertext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return plaintext.decode()
