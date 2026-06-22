"""
Review runner: orchestrates one evaluation end-to-end.

ingest(load) -> per-criterion grade + evidence verification -> deterministic
decision -> persist. Emits live events through an optional ``emit`` callback
(wired to the event bus in P4). Every dependency is a port, so the whole runner
is exercised offline with ``FakeLLM`` in tests.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ReviewStatus
from app.db.models import CriterionResult, Evidence, Review, ReviewEvent
from app.db.repositories.tasks import TaskRepository
from app.engine.evidence import verify_evidence
from app.engine.grader import grade_criterion
from app.engine.policy import GradedCriterion, decide
from app.engine.prompts import PROMPT_TEMPLATE_VERSION
from app.ingestion.loader import load_fileset
from app.llm import get_llm
from app.services.provider_configs import resolve_credentials
from app.settings import get_settings
from app.utils.logger import setup_logger

logger = setup_logger("app.engine.runner")

EmitFn = Callable[[str, dict], Awaitable[None]]


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _emit(emit: Optional[EmitFn], event_type: str, payload: dict) -> None:
    if emit is not None:
        await emit(event_type, payload)


async def run_review(
    session: AsyncSession, review_id: str, *, emit: Optional[EmitFn] = None
) -> Review:
    settings = get_settings()
    review = await session.get(Review, review_id)
    if review is None:
        raise ValueError(f"Review {review_id} not found")

    try:
        review.status = ReviewStatus.RUNNING
        review.started_at = _now()
        review.engine_version = settings.engine_version
        review.prompt_template_version = PROMPT_TEMPLATE_VERSION
        await session.commit()

        # Idempotent re-run: clear any prior partial results/events for this review.
        prior_ids = (
            await session.execute(
                select(CriterionResult.id).where(CriterionResult.review_id == review_id)
            )
        ).scalars().all()
        if prior_ids:
            await session.execute(
                delete(Evidence).where(Evidence.criterion_result_id.in_(prior_ids))
            )
            await session.execute(
                delete(CriterionResult).where(CriterionResult.review_id == review_id)
            )
        await session.execute(
            delete(ReviewEvent).where(ReviewEvent.review_id == review_id)
        )
        await session.commit()

        version = await TaskRepository(session).get_version(review.rubric_version_id)
        if version is None:
            raise ValueError("Rubric version not found")
        fileset = await load_fileset(session, review.submission_id)
        if fileset is None or not fileset.files:
            raise ValueError("Submission has no analyzable files")

        await _emit(
            emit,
            "review_started",
            {
                "review_id": review.id,
                "total_criteria": len(version.criteria),
                "model_id": review.model_id,
            },
        )

        llm = get_llm()
        _, api_key = await resolve_credentials(session)
        graded: list[GradedCriterion] = []
        total = len(version.criteria)

        for idx, crit in enumerate(version.criteria):
            await _emit(
                emit,
                "criterion_started",
                {"key": crit.key, "title": crit.title, "index": idx, "total": total},
            )
            outcome = await grade_criterion(
                llm, crit, fileset.files, model_id=review.model_id, api_key=api_key
            )
            verified = verify_evidence(outcome.evidence, fileset)

            result = CriterionResult(
                review_id=review.id,
                criterion_id=crit.id,
                criterion_key=crit.key,
                verdict=outcome.verdict,
                score=outcome.score,
                confidence=outcome.confidence,
                raw_judgment=outcome.raw,
                model_id=outcome.model_id,
                latency_ms=outcome.latency_ms,
                attempts=outcome.attempts,
                repaired=outcome.repaired,
            )
            session.add(result)
            await session.flush()
            for ve in verified:
                session.add(
                    Evidence(
                        criterion_result_id=result.id,
                        path=ve.path,
                        start_line=ve.start_line,
                        end_line=ve.end_line,
                        quote=ve.quote,
                        verified=ve.verified,
                        resolved_file_hash=ve.resolved_file_hash,
                    )
                )
            await session.commit()

            graded.append(
                GradedCriterion(
                    key=crit.key,
                    type=crit.type,
                    verdict=outcome.verdict,
                    score=outcome.score,
                    weight=crit.weight,
                    gate_policy=crit.gate_policy,
                )
            )
            await _emit(
                emit,
                "criterion_completed",
                {
                    "criterion_id": crit.id,
                    "key": crit.key,
                    "result": {
                        "verdict": outcome.verdict.value,
                        "score": outcome.score,
                        "confidence": outcome.confidence,
                        "type": crit.type.value,
                        "weight": crit.weight,
                    },
                    "evidence": [
                        {"path": ve.path, "start_line": ve.start_line,
                         "end_line": ve.end_line, "verified": ve.verified.value}
                        for ve in verified
                    ],
                    "repaired": outcome.repaired,
                    "attempts": outcome.attempts,
                },
            )

        decision_config = version.decision_config or {}
        result = decide(
            graded,
            accept_at=float(decision_config.get("accept_at", 70)),
            review_at=float(decision_config.get("review_at", 50)),
        )
        review.decision = result.decision
        review.final_score = result.final_score
        review.gate_failed = result.gate_failed
        review.decision_breakdown = result.breakdown
        review.status = ReviewStatus.COMPLETED
        review.completed_at = _now()
        await session.commit()

        await _emit(
            emit,
            "decision_computed",
            {
                "decision": result.decision.value,
                "final_score": result.final_score,
                "gate_failed": result.gate_failed,
                "breakdown": result.breakdown,
            },
        )
        await _emit(
            emit,
            "review_completed",
            {"review_id": review.id, "decision": result.decision.value,
             "final_score": result.final_score},
        )
        return review

    except Exception as exc:  # noqa: BLE001 - record failure, never crash the worker
        logger.error(f"Review {review_id} failed: {exc}")
        review.status = ReviewStatus.FAILED
        review.error_message = str(exc)[:1000]
        review.completed_at = _now()
        await session.commit()
        await _emit(emit, "review_failed", {"review_id": review.id, "error": str(exc)})
        return review
