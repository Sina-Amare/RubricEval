"""
Test configuration.

Uses a temporary file-backed SQLite database (set before the app imports its
settings) so the async engine behaves like a real DB across connections.
Integration tests can additionally target PostgreSQL by exporting
``TEST_DATABASE_URL`` / ``DATABASE_URL`` before running pytest.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

# Configure the environment BEFORE importing anything that reads settings.
_DB_FILE = Path(tempfile.gettempdir()) / "rubric_eval_test.db"
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_DB_FILE.as_posix()}")
os.environ.setdefault("AUTO_MIGRATE", "false")
os.environ.setdefault("OPERATOR_TOKEN", "test-token")
os.environ.setdefault("LLM_BACKEND", "fake")
os.environ.setdefault(
    "BLOB_DIR", str(Path(tempfile.gettempdir()) / "rubric_eval_test_blobs")
)

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.db.base import dispose_engine  # noqa: E402
from app.db.init_db import create_all, drop_all  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture
async def prepared_db():
    await create_all()
    try:
        yield
    finally:
        await drop_all()
        await dispose_engine()


@pytest_asyncio.fixture
async def client(prepared_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token"}
