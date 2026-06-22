"""Review repository (with eager-loaded results + evidence)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import CriterionResult, Review


class ReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, review: Review) -> Review:
        self.session.add(review)
        await self.session.commit()
        await self.session.refresh(review)
        return review

    async def get(self, review_id: str) -> Optional[Review]:
        result = await self.session.execute(
            select(Review)
            .options(
                selectinload(Review.results).selectinload(CriterionResult.evidence)
            )
            .where(Review.id == review_id)
        )
        return result.scalar_one_or_none()

    async def get_by_idempotency(self, key: str) -> Optional[Review]:
        result = await self.session.execute(
            select(Review)
            .options(
                selectinload(Review.results).selectinload(CriterionResult.evidence)
            )
            .where(Review.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def list(
        self, task_id: Optional[str] = None, limit: int = 50
    ) -> list[Review]:
        query = select(Review).order_by(Review.created_at.desc()).limit(limit)
        if task_id:
            query = query.where(Review.task_id == task_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())
