"""Review creation + report endpoints (operator-only)."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_operator
from app.api.schemas.review import (
    CreateReviewIn,
    CriterionResultOut,
    EvidenceOut,
    ReviewOut,
    ReviewSummaryOut,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.db.base import get_sessionmaker
from app.db.models import Review
from app.db.repositories.events import list_events
from app.db.repositories.reviews import ReviewRepository
from app.events.bus import get_event_bus
from app.services.reviews import create_review

_TERMINAL_EVENTS = {"review_completed", "review_failed"}


def _sse_frame(event_id: int, event_type: str, payload: dict) -> str:
    return (
        f"id: {event_id}\n"
        f"event: {event_type}\n"
        f"data: {json.dumps(payload)}\n\n"
    )

router = APIRouter(prefix="/reviews", tags=["reviews"], dependencies=[Depends(require_operator)])


def _result_out(r) -> CriterionResultOut:
    rationale = ""
    if isinstance(r.raw_judgment, dict):
        rationale = str(r.raw_judgment.get("rationale", ""))
    return CriterionResultOut(
        criterion_id=r.criterion_id,
        criterion_key=r.criterion_key,
        verdict=r.verdict,
        score=r.score,
        confidence=r.confidence,
        rationale=rationale,
        latency_ms=r.latency_ms,
        repaired=r.repaired,
        evidence=[
            EvidenceOut(
                path=e.path,
                start_line=e.start_line,
                end_line=e.end_line,
                quote=e.quote,
                verified=e.verified,
            )
            for e in r.evidence
        ],
    )


def _review_out(review: Review) -> ReviewOut:
    return ReviewOut(
        id=review.id,
        task_id=review.task_id,
        rubric_version_id=review.rubric_version_id,
        submission_id=review.submission_id,
        status=review.status,
        decision=review.decision,
        final_score=review.final_score,
        gate_failed=review.gate_failed,
        decision_breakdown=review.decision_breakdown,
        model_id=review.model_id,
        prompt_template_version=review.prompt_template_version,
        rubric_content_hash=review.rubric_content_hash,
        engine_version=review.engine_version,
        error_message=review.error_message,
        created_at=review.created_at,
        started_at=review.started_at,
        completed_at=review.completed_at,
        results=[_result_out(r) for r in sorted(review.results, key=lambda x: x.criterion_key)],
    )


@router.post("", response_model=ReviewOut, status_code=201)
async def post_review(
    body: CreateReviewIn, session: AsyncSession = Depends(get_session)
) -> ReviewOut:
    try:
        review = await create_review(
            session, task_id=body.task_id, submission_id=body.submission_id
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    full = await ReviewRepository(session).get(review.id)
    return _review_out(full)


@router.get("/{review_id}", response_model=ReviewOut)
async def get_review(
    review_id: str, session: AsyncSession = Depends(get_session)
) -> ReviewOut:
    review = await ReviewRepository(session).get(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return _review_out(review)


@router.get("", response_model=list[ReviewSummaryOut])
async def list_reviews(
    task_id: str | None = None, session: AsyncSession = Depends(get_session)
) -> list[ReviewSummaryOut]:
    reviews = await ReviewRepository(session).list(task_id=task_id)
    return [
        ReviewSummaryOut(
            id=r.id,
            task_id=r.task_id,
            submission_id=r.submission_id,
            status=r.status,
            decision=r.decision,
            final_score=r.final_score,
            created_at=r.created_at,
            completed_at=r.completed_at,
        )
        for r in reviews
    ]


@router.get("/{review_id}/events")
async def get_events(
    review_id: str, after: int = 0, session: AsyncSession = Depends(get_session)
) -> list[dict]:
    """Replay the durable event log (backs reconnect / report timeline)."""
    events = await list_events(session, review_id, after)
    return [
        {"id": e.id, "seq": e.seq, "type": e.type, "payload": e.payload}
        for e in events
    ]


@router.get("/{review_id}/stream")
async def stream_review(review_id: str, request: Request) -> StreamingResponse:
    """Live SSE stream: replay missed events, then tail live ones."""
    bus = get_event_bus()
    queue = bus.subscribe(review_id)
    sessionmaker = get_sessionmaker()

    last_id = 0
    leid = request.headers.get("last-event-id") or request.query_params.get("after", "")
    if leid.isdigit():
        last_id = int(leid)

    async def gen():
        nonlocal last_id
        try:
            async with sessionmaker() as session:
                for e in await list_events(session, review_id, last_id):
                    last_id = e.id
                    yield _sse_frame(e.id, e.type, e.payload)
                    if e.type in _TERMINAL_EVENTS:
                        return
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                if data["id"] <= last_id:
                    continue
                last_id = data["id"]
                yield _sse_frame(data["id"], data["type"], data["payload"])
                if data["type"] in _TERMINAL_EVENTS:
                    break
        finally:
            bus.unsubscribe(review_id, queue)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
