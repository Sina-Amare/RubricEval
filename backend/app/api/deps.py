"""Shared FastAPI dependencies."""

from __future__ import annotations

from app.db.base import get_session  # noqa: F401  (re-exported for routers)
from app.security.auth import require_operator  # noqa: F401
from app.settings import get_settings  # noqa: F401
