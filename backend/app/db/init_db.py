"""
Schema bootstrap.

``create_all`` is idempotent and portable; it is used on startup when
``auto_migrate`` is enabled (the no-Docker quick-start path) and by the test
suite. The Alembic baseline migration creates the same schema, so the two
paths converge.
"""

from __future__ import annotations

from app.db import models  # noqa: F401  (import registers all tables on Base.metadata)
from app.db.base import Base, get_engine


async def create_all() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
