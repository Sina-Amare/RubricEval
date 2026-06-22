"""Create a review (idempotent) and run it.

In P3 the run is synchronous; in P4 creation enqueues a durable job and the
worker calls ``run_review``. The dedup/idempotency logic lives here so both
paths share it.
"""

from __future__ import annotations

import hashlib

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ReviewStatus
from app.core.exceptions import NotFoundError, ValidationError
from app.db.models import Review, Submission, Task
from app.db.repositories.reviews import ReviewRepository
from app.db.repositories.tasks import TaskRepository
from app.engine.prompts import PROMPT_TEMPLATE_VERSION
from app.jobs.queue import enqueue
from app.services.provider_configs import resolve_credentials


def _idempotency_key(version_id: str, submission_id: str, model_id: str) -> str:
    raw = f"{version_id}:{submission_id}:{model_id}:{PROMPT_TEMPLATE_VERSION}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def create_review(session: AsyncSession, *, task_id: str, submission_id: str) -> Review:
    task = await session.get(Task, task_id)
    if task is None:
        raise NotFoundError("Task not found")
    if not task.current_rubric_version_id:
        raise ValidationError("Task has no published rubric version")
    if await session.get(Submission, submission_id) is None:
        raise NotFoundError("Submission not found")

    version = await TaskRepository(session).get_version(task.current_rubric_version_id)
    model_id, _ = await resolve_credentials(session)
    idem = _idempotency_key(version.id, submission_id, model_id)

    repo = ReviewRepository(session)
    existing = await repo.get_by_idempotency(idem)
    if existing is not None:
        if existing.status == ReviewStatus.COMPLETED:
            return existing
        # Re-arm the job for a queued/failed review.
        await enqueue(session, existing.id)
        return existing

    review = Review(
        task_id=task_id,
        rubric_version_id=version.id,
        submission_id=submission_id,
        status=ReviewStatus.QUEUED,
        model_id=model_id,
        rubric_content_hash=version.content_hash,
        idempotency_key=idem,
    )
    review = await repo.create(review)
    await enqueue(session, review.id)
    return review
