"""Review-event repository (append-only durable log)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ReviewEvent


async def append_event(
    session: AsyncSession, review_id: str, event_type: str, payload: dict
) -> ReviewEvent:
    max_seq = await session.scalar(
        select(func.max(ReviewEvent.seq)).where(ReviewEvent.review_id == review_id)
    )
    event = ReviewEvent(
        review_id=review_id, seq=(max_seq or 0) + 1, type=event_type, payload=payload
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event


async def list_events(
    session: AsyncSession, review_id: str, after_id: int = 0
) -> list[ReviewEvent]:
    result = await session.execute(
        select(ReviewEvent)
        .where(ReviewEvent.review_id == review_id, ReviewEvent.id > after_id)
        .order_by(ReviewEvent.id)
    )
    return list(result.scalars().all())
