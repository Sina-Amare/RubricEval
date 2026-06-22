"""Submission + submission-file repository."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Submission, SubmissionFile


class SubmissionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, submission: Submission, files: list[SubmissionFile]
    ) -> Submission:
        self.session.add(submission)
        await self.session.flush()
        for f in files:
            f.submission_id = submission.id
            self.session.add(f)
        await self.session.commit()
        return await self.get(submission.id)  # type: ignore[return-value]

    async def get(self, submission_id: str) -> Optional[Submission]:
        result = await self.session.execute(
            select(Submission)
            .options(selectinload(Submission.files))
            .where(Submission.id == submission_id)
        )
        return result.scalar_one_or_none()

    async def get_by_fileset_hash(self, fileset_hash: str) -> Optional[Submission]:
        result = await self.session.execute(
            select(Submission)
            .options(selectinload(Submission.files))
            .where(Submission.fileset_hash == fileset_hash)
            .order_by(Submission.created_at.desc())
        )
        return result.scalars().first()

    async def get_file(self, submission_id: str, path: str) -> Optional[SubmissionFile]:
        result = await self.session.execute(
            select(SubmissionFile).where(
                SubmissionFile.submission_id == submission_id,
                SubmissionFile.path == path,
            )
        )
        return result.scalar_one_or_none()
