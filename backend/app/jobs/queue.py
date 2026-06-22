"""
Durable leased-job queue on the database.

On PostgreSQL the claim uses ``SELECT ... FOR UPDATE SKIP LOCKED`` for
contention-free multi-worker leasing. On SQLite (single-worker no-Docker mode)
a plain serialized claim is sufficient. Crashed leases are reclaimed by
``reclaim_orphans`` so no work is lost.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import JobState
from app.db.models import Job
from app.settings import get_settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def enqueue(session: AsyncSession, review_id: str) -> Job:
    """Create or re-arm the job for a review (idempotent on review_id)."""
    job = await session.scalar(select(Job).where(Job.review_id == review_id))
    if job is None:
        job = Job(
            review_id=review_id,
            state=JobState.QUEUED,
            max_attempts=get_settings().job_max_attempts,
            available_at=_now(),
        )
        session.add(job)
    else:
        job.state = JobState.QUEUED
        job.available_at = _now()
    await session.commit()
    await session.refresh(job)
    return job


async def claim_next(
    session: AsyncSession, owner: str, lease_seconds: int
) -> Optional[Job]:
    now = _now()
    query = (
        select(Job)
        .where(Job.state == JobState.QUEUED, Job.available_at <= now)
        .order_by(Job.created_at)
        .limit(1)
    )
    if not get_settings().is_sqlite:
        query = query.with_for_update(skip_locked=True)
    job = await session.scalar(query)
    if job is None:
        return None
    job.state = JobState.LEASED
    job.lease_owner = owner
    job.leased_until = now + timedelta(seconds=lease_seconds)
    job.attempts += 1
    await session.commit()
    await session.refresh(job)
    return job


async def complete(session: AsyncSession, job_id: str) -> None:
    job = await session.get(Job, job_id)
    if job is not None:
        job.state = JobState.DONE
        await session.commit()


async def fail_or_retry(
    session: AsyncSession, job_id: str, backoff_seconds: int = 5
) -> None:
    job = await session.get(Job, job_id)
    if job is None:
        return
    if job.attempts >= job.max_attempts:
        job.state = JobState.FAILED
    else:
        job.state = JobState.QUEUED
        job.available_at = _now() + timedelta(seconds=backoff_seconds)
    await session.commit()


async def reclaim_orphans(session: AsyncSession) -> int:
    """Requeue jobs whose lease expired (worker crashed mid-run)."""
    now = _now()
    result = await session.execute(
        select(Job).where(Job.state == JobState.LEASED, Job.leased_until < now)
    )
    jobs = list(result.scalars().all())
    for job in jobs:
        job.state = JobState.QUEUED
        job.available_at = now
    await session.commit()
    return len(jobs)
