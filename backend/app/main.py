"""
FastAPI application factory.

Wires routers, CORS, and a lifespan that (optionally) creates the schema and,
in later phases, starts the embedded worker. Importing this module has no
side effects; the app is built by ``create_app()``.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import (
    health,
    provider_configs,
    reviews,
    submissions,
    tasks,
)
from app.db.base import dispose_engine
from app.db.init_db import create_all
from app.jobs.worker import Worker
from app.settings import get_settings
from app.utils.logger import setup_logger

logger = setup_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.auto_migrate:
        logger.info("auto_migrate enabled: ensuring schema exists")
        await create_all()

    stop_event: asyncio.Event | None = None
    worker_task: asyncio.Task | None = None
    if settings.embedded_worker:
        stop_event = asyncio.Event()
        worker_task = asyncio.create_task(Worker().run_forever(stop_event))
        logger.info("Embedded worker started")

    try:
        yield
    finally:
        if stop_event is not None and worker_task is not None:
            stop_event.set()
            try:
                await asyncio.wait_for(worker_task, timeout=10)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                worker_task.cancel()
        await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Rubric Evaluation API",
        version=settings.engine_version,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=r"http://localhost:\d+",  # any local port (multi-project dev)
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix="/api")
    app.include_router(tasks.router, prefix="/api")
    app.include_router(submissions.router, prefix="/api")
    app.include_router(reviews.router, prefix="/api")
    app.include_router(provider_configs.router, prefix="/api")
    return app


app = create_app()
