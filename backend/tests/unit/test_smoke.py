"""P0 smoke tests: the app boots, the schema builds, and /health is green."""

from __future__ import annotations

from app.core.enums import CriterionType, Decision, Verdict
from app.settings import Settings


def test_enums_are_string_valued():
    assert CriterionType.GATE.value == "gate"
    assert Verdict.ERROR.value == "error"
    assert Decision.ACCEPT.value == "accept"


def test_settings_sync_url_derivation():
    s = Settings(database_url="sqlite+aiosqlite:///./data/app.db")
    assert s.sync_database_url == "sqlite:///./data/app.db"
    assert s.is_sqlite is True
    pg = Settings(database_url="postgresql+asyncpg://u:p@h/db")
    assert pg.sync_database_url.startswith("postgresql+psycopg://")
    assert pg.is_sqlite is False


async def test_health_ready(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is True
    assert body["checks"]["database"] is True
