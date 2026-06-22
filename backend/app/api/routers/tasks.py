"""Task CRUD + rubric draft/publish/versions endpoints (operator-only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_operator
from app.api.schemas.task import (
    CriterionOut,
    DecisionConfig,
    PublishResult,
    RubricDraft,
    RubricVersionOut,
    TaskCreate,
    TaskOut,
    TaskUpdate,
)
from app.core.exceptions import ValidationError
from app.db.models import Criterion, RubricVersion, Task
from app.db.repositories.tasks import TaskRepository

router = APIRouter(prefix="/tasks", tags=["tasks"], dependencies=[Depends(require_operator)])


# --- mappers --------------------------------------------------------------
def _task_out(task: Task, version_number: int | None = None) -> TaskOut:
    return TaskOut(
        id=task.id,
        name=task.name,
        description=task.description,
        current_rubric_version_id=task.current_rubric_version_id,
        current_version_number=version_number,
        draft=RubricDraft(**(task.draft or {})),
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _criterion_out(c: Criterion) -> CriterionOut:
    return CriterionOut(
        id=c.id,
        key=c.key,
        title=c.title,
        instructions=c.instructions,
        type=c.type,
        weight=c.weight,
        gate_policy=c.gate_policy,
        pass_threshold=c.pass_threshold,
        order_index=c.order_index,
    )


def _version_out(v: RubricVersion) -> RubricVersionOut:
    return RubricVersionOut(
        id=v.id,
        version_number=v.version_number,
        content_hash=v.content_hash,
        prompt_template_version=v.prompt_template_version,
        decision_config=DecisionConfig(**v.decision_config),
        criteria=[_criterion_out(c) for c in v.criteria],
        created_at=v.created_at,
    )


async def _get_task_or_404(repo: TaskRepository, task_id: str) -> Task:
    task = await repo.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# --- task CRUD ------------------------------------------------------------
@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(body: TaskCreate, session: AsyncSession = Depends(get_session)) -> TaskOut:
    repo = TaskRepository(session)
    task = await repo.create(body.name, body.description)
    return _task_out(task)


@router.get("", response_model=list[TaskOut])
async def list_tasks(session: AsyncSession = Depends(get_session)) -> list[TaskOut]:
    repo = TaskRepository(session)
    tasks = await repo.list()
    # Resolve current published version numbers so the dashboard shows
    # "published vN" instead of "draft" for tasks that have been published.
    version_ids = [t.current_rubric_version_id for t in tasks if t.current_rubric_version_id]
    numbers: dict[str, int] = {}
    if version_ids:
        rows = await session.execute(
            select(RubricVersion.id, RubricVersion.version_number).where(
                RubricVersion.id.in_(version_ids)
            )
        )
        numbers = {row[0]: row[1] for row in rows.all()}
    return [_task_out(t, numbers.get(t.current_rubric_version_id)) for t in tasks]


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(task_id: str, session: AsyncSession = Depends(get_session)) -> TaskOut:
    repo = TaskRepository(session)
    task = await _get_task_or_404(repo, task_id)
    version_number = None
    if task.current_rubric_version_id:
        v = await repo.get_version(task.current_rubric_version_id)
        version_number = v.version_number if v else None
    return _task_out(task, version_number)


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: str, body: TaskUpdate, session: AsyncSession = Depends(get_session)
) -> TaskOut:
    repo = TaskRepository(session)
    task = await _get_task_or_404(repo, task_id)
    task = await repo.update(task, body.name, body.description)
    return _task_out(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: str, session: AsyncSession = Depends(get_session)) -> None:
    repo = TaskRepository(session)
    task = await _get_task_or_404(repo, task_id)
    await repo.delete(task)


# --- rubric draft + publish ----------------------------------------------
@router.get("/{task_id}/rubric", response_model=RubricDraft)
async def get_rubric_draft(
    task_id: str, session: AsyncSession = Depends(get_session)
) -> RubricDraft:
    repo = TaskRepository(session)
    task = await _get_task_or_404(repo, task_id)
    return RubricDraft(**(task.draft or {}))


@router.put("/{task_id}/rubric", response_model=RubricDraft)
async def save_rubric_draft(
    task_id: str, draft: RubricDraft, session: AsyncSession = Depends(get_session)
) -> RubricDraft:
    repo = TaskRepository(session)
    task = await _get_task_or_404(repo, task_id)
    await repo.save_draft(task, draft)
    return draft


@router.post("/{task_id}/rubric/publish", response_model=PublishResult)
async def publish_rubric(
    task_id: str, session: AsyncSession = Depends(get_session)
) -> PublishResult:
    repo = TaskRepository(session)
    task = await _get_task_or_404(repo, task_id)
    draft = RubricDraft(**(task.draft or {}))
    try:
        version = await repo.publish(task, draft)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return PublishResult(
        rubric_version_id=version.id,
        version_number=version.version_number,
        content_hash=version.content_hash,
    )


@router.get("/{task_id}/rubric/versions", response_model=list[RubricVersionOut])
async def list_versions(
    task_id: str, session: AsyncSession = Depends(get_session)
) -> list[RubricVersionOut]:
    repo = TaskRepository(session)
    await _get_task_or_404(repo, task_id)
    return [_version_out(v) for v in await repo.list_versions(task_id)]


@router.get("/{task_id}/rubric/versions/{version_id}", response_model=RubricVersionOut)
async def get_version(
    task_id: str, version_id: str, session: AsyncSession = Depends(get_session)
) -> RubricVersionOut:
    repo = TaskRepository(session)
    version = await repo.get_version(version_id)
    if version is None or version.task_id != task_id:
        raise HTTPException(status_code=404, detail="Rubric version not found")
    return _version_out(version)
