"""
BYOK key encryption (Fernet, AES-128-CBC + HMAC).

The symmetric key is derived from ``APP_SECRET_KEY`` so the only secret to
manage is that env var. Plaintext API keys are never stored or returned; only
ciphertext + a short fingerprint (last 4 chars) are persisted.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from app.settings import get_settings


def _fernet() -> Fernet:
    secret = get_settings().app_secret_key.encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def encrypt(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode("utf-8"))


def decrypt(ciphertext: bytes) -> str:
    return _fernet().decrypt(ciphertext).decode("utf-8")


def fingerprint(api_key: str) -> str:
    if not api_key:
        return ""
    tail = api_key[-4:] if len(api_key) >= 4 else api_key
    return f"…{tail}"
