"""Health / readiness probe (public, unauthenticated)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.settings import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Return 200 only when required dependencies are reachable."""
    checks: dict[str, bool] = {}
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False

    ready = all(checks.values())
    return {
        "status": "ok" if ready else "degraded",
        "ready": ready,
        "checks": checks,
        "engine_version": settings.engine_version,
        "llm_backend": settings.llm_backend,
        "default_model": settings.default_model,
    }
