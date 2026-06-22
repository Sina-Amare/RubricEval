"""
Single-operator authentication.

A shared bearer token (``OPERATOR_TOKEN``) protects all mutating and read
routes except ``/health``. The SSE endpoint also accepts the token as a query
parameter because ``EventSource`` cannot set headers.
"""

from __future__ import annotations

import hmac
from typing import Optional

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.settings import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)


def _token_matches(candidate: Optional[str], expected: str) -> bool:
    if not candidate:
        return False
    return hmac.compare_digest(candidate, expected)


async def require_operator(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    token: Optional[str] = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    """Authorize a request via ``Authorization: Bearer`` or ``?token=``."""
    candidate = creds.credentials if creds else token
    if not _token_matches(candidate, settings.operator_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing operator token",
            headers={"WWW-Authenticate": "Bearer"},
        )
