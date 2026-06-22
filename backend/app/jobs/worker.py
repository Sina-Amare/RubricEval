"""
The review worker.

Leases a job, runs the review with a live ``emit`` callback, then marks the job
done (or retries on failure). ``run_forever`` drives it as a background task
(embedded in the API process for no-Docker, or as a standalone process under
Docker). ``drain_jobs`` runs the queue to empty — used by tests for determinism.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.enums import ReviewStatus
from app.db.base import get_sessionmaker
from app.engine.runner import run_review
from app.events.bus import EventBus, get_event_bus
from app.events.emitter import make_emitter
from app.jobs import queue as q
from app.notify.telegram import notify_review_complete
from app.settings import get_settings
from app.utils.logger import setup_logger

logger = setup_logger("app.jobs.worker")


class Worker:
    def __init__(
        self,
        sessionmaker: Optional[async_sessionmaker] = None,
        bus: Optional[EventBus] = None,
        owner: Optional[str] = None,
    ) -> None:
        self.sm = sessionmaker or get_sessionmaker()
        self.bus = bus or get_event_bus()
        self.owner = owner or f"worker-{uuid.uuid4().hex[:8]}"
        self.settings = get_settings()

    async def run_once(self) -> bool:
        """Process at most one job. Returns True if a job was handled."""
        async with self.sm() as session:
            job = await q.claim_next(session, self.owner, self.settings.job_lease_seconds)
            if job is None:
                return False
            job_id, review_id = job.id, job.review_id

        ok = False
        try:
            emit = make_emitter(self.sm, self.bus, review_id)
            async with self.sm() as session:
                review = await run_review(session, review_id, emit=emit)
            ok = review.status == ReviewStatus.COMPLETED
            if ok:
                await notify_review_complete(review)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Job {job_id} crashed: {exc}")
            ok = False

        async with self.sm() as session:
            if ok:
                await q.complete(session, job_id)
            else:
                await q.fail_or_retry(session, job_id)
        return True

    async def run_forever(self, stop: asyncio.Event) -> None:
        async with self.sm() as session:
            reclaimed = await q.reclaim_orphans(session)
        if reclaimed:
            logger.info(f"Reclaimed {reclaimed} orphaned job(s) on startup")
        logger.info(f"Worker {self.owner} started")
        while not stop.is_set():
            try:
                handled = await self.run_once()
            except Exception as exc:  # noqa: BLE001 - never let the loop die
                logger.error(f"Worker loop error: {exc}")
                handled = False
            if not handled:
                try:
                    await asyncio.wait_for(
                        stop.wait(), timeout=self.settings.worker_poll_interval
                    )
                except asyncio.TimeoutError:
                    pass
        logger.info(f"Worker {self.owner} stopped")


async def drain_jobs(bus: Optional[EventBus] = None) -> int:
    """Run the queue to empty (single-threaded). Used in tests."""
    worker = Worker(bus=bus)
    count = 0
    while await worker.run_once():
        count += 1
    return count
