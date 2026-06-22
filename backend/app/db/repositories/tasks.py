"""Task + rubric-version repository."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.schemas.task import RubricDraft
from app.db.models import Criterion, RubricVersion, Task
from app.services.rubric import rubric_hash, validate_publishable


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- tasks ------------------------------------------------------------
    async def create(self, name: str, description: str = "") -> Task:
        task = Task(name=name, description=description, draft=_empty_draft())
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def get(self, task_id: str) -> Optional[Task]:
        return await self.session.get(Task, task_id)

    async def list(self) -> list[Task]:
        result = await self.session.execute(select(Task).order_by(Task.created_at.desc()))
        return list(result.scalars().all())

    async def update(
        self, task: Task, name: Optional[str], description: Optional[str]
    ) -> Task:
        if name is not None:
            task.name = name
        if description is not None:
            task.description = description
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def delete(self, task: Task) -> None:
        await self.session.delete(task)
        await self.session.commit()

    async def save_draft(self, task: Task, draft: RubricDraft) -> Task:
        task.draft = draft.model_dump(mode="json")
        await self.session.commit()
        await self.session.refresh(task)
        return task

    # --- rubric versions --------------------------------------------------
    async def publish(self, task: Task, draft: RubricDraft) -> RubricVersion:
        validate_publishable(draft)
        content_hash = rubric_hash(draft)

        max_v = await self.session.scalar(
            select(func.max(RubricVersion.version_number)).where(
                RubricVersion.task_id == task.id
            )
        )
        version = RubricVersion(
            task_id=task.id,
            version_number=(max_v or 0) + 1,
            content_hash=content_hash,
            decision_config=draft.decision_config.model_dump(mode="json"),
            prompt_template_version=draft.prompt_template_version,
            is_published=True,
        )
        self.session.add(version)
        await self.session.flush()  # assign version.id

        for idx, c in enumerate(draft.criteria):
            self.session.add(
                Criterion(
                    rubric_version_id=version.id,
                    key=c.key,
                    title=c.title,
                    instructions=c.instructions,
                    type=c.type,
                    weight=c.weight,
                    gate_policy=c.gate_policy,
                    pass_threshold=c.pass_threshold,
                    order_index=idx,
                )
            )
        # Persist the draft too, so the editable state matches what was published.
        task.draft = draft.model_dump(mode="json")
        task.current_rubric_version_id = version.id
        await self.session.commit()
        return await self.get_version(version.id)  # type: ignore[return-value]

    async def get_version(self, version_id: str) -> Optional[RubricVersion]:
        result = await self.session.execute(
            select(RubricVersion)
            .options(selectinload(RubricVersion.criteria))
            .where(RubricVersion.id == version_id)
        )
        return result.scalar_one_or_none()

    async def list_versions(self, task_id: str) -> list[RubricVersion]:
        result = await self.session.execute(
            select(RubricVersion)
            .options(selectinload(RubricVersion.criteria))
            .where(RubricVersion.task_id == task_id)
            .order_by(RubricVersion.version_number.desc())
        )
        return list(result.scalars().all())


def _empty_draft() -> dict:
    return RubricDraft().model_dump(mode="json")
