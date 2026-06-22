"""Unit tests for BYOK key encryption and log masking."""

from __future__ import annotations

import logging

from app.security.crypto import decrypt, encrypt, fingerprint
from app.utils.logger import SensitiveDataFilter


def test_encrypt_roundtrip():
    cipher = encrypt("sk-or-secret-123456")
    assert cipher != b"sk-or-secret-123456"
    assert decrypt(cipher) == "sk-or-secret-123456"


def test_fingerprint_hides_key():
    fp = fingerprint("sk-or-abcd1234")
    assert fp.endswith("1234")
    assert "abcd" not in fp


def test_logger_masks_openrouter_key():
    record = logging.LogRecord(
        "n", logging.INFO, "p", 1, "using key sk-or-abcdef123456789 now", None, None
    )
    SensitiveDataFilter().filter(record)
    msg = record.getMessage()
    assert "sk-or-abcdef123456789" not in msg
    assert "REDACTED" in msg


def test_logger_masks_bearer_token():
    record = logging.LogRecord(
        "n", logging.INFO, "p", 1, "Authorization: Bearer abc.def.ghi", None, None
    )
    SensitiveDataFilter().filter(record)
    assert "abc.def.ghi" not in record.getMessage()
