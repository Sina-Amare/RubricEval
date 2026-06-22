"""
Logging setup with sensitive-data masking.

Generalized from the original ``src/utils/logger.py``: the Telegram/file
machinery is dropped in favor of stdout JSON-ish logging, and the masking
patterns are extended to cover BYOK API keys and bearer tokens so a key can
never leak into the logs.
"""

from __future__ import annotations

import logging
import re
import sys

_SENSITIVE_PATTERNS = [
    re.compile(r"sk-or-[A-Za-z0-9\-_]{8,}"),          # OpenRouter keys
    re.compile(r"sk-[A-Za-z0-9]{16,}"),               # OpenAI-style keys
    re.compile(r"Bearer\s+[A-Za-z0-9\-_\.=]+", re.I),  # bearer tokens
    re.compile(r"(api[_-]?key\"?\s*[:=]\s*\"?)[^\s\"&]+", re.I),
]
_MASK = "***REDACTED***"


class SensitiveDataFilter(logging.Filter):
    """Redacts secrets from log messages before they are emitted."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # pragma: no cover - defensive
            return True
        redacted = msg
        for pattern in _SENSITIVE_PATTERNS:
            redacted = pattern.sub(_MASK, redacted)
        if redacted != msg:
            record.msg = redacted
            record.args = ()
        return True


_CONFIGURED: set[str] = set()


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a configured logger that masks secrets and writes to stdout."""
    logger = logging.getLogger(name)
    if name in _CONFIGURED:
        return logger
    logger.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    handler.addFilter(SensitiveDataFilter())
    logger.addHandler(handler)
    logger.propagate = False
    _CONFIGURED.add(name)
    return logger
