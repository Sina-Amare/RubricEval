"""
Application exception hierarchy.

Ported and generalized from the original ``src/core/exceptions.py``: the
hiring-specific semantics are dropped, and engine-specific errors
(ingestion / LLM / policy / evidence) are added.
"""

from __future__ import annotations

from typing import Any, Optional


class AppError(Exception):
    """Base class for all application errors."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(AppError):
    """Invalid or missing configuration."""


class ValidationError(AppError):
    """User input failed validation."""


class NotFoundError(AppError):
    """A requested entity does not exist."""


class StorageError(AppError):
    """A database operation failed."""


class IngestionError(AppError):
    """Fetching/normalizing a submission failed (clone, unzip, caps)."""


class LLMError(AppError):
    """An LLM call failed in a non-retryable way."""


class RateLimitError(LLMError):
    """An LLM provider rate-limited the request (retryable)."""

    def __init__(
        self,
        message: str,
        retry_after: Optional[float] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, details)
        self.retry_after = retry_after


class PolicyError(AppError):
    """The deterministic decision policy received inconsistent inputs."""


class EvidenceError(AppError):
    """Evidence verification encountered an unexpected condition."""
