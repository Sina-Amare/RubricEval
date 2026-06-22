"""
Per-criterion grader.

Builds the grading prompt, calls the LLM port, validates the result against
``CriterionJudgment``, and returns a normalized outcome. Parsing/repair of the
raw model text lives in the LLM client; here we validate the structured dict and
fall back to an ERROR verdict if it is unusable (never a silent pass).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.core.enums import Verdict
from app.engine.prompts import build_messages
from app.engine.schemas import CriterionJudgment, EvidenceItem
from app.interfaces.llm import LLMPort


@dataclass
class GradeOutcome:
    verdict: Verdict
    score: float | None
    confidence: float
    rationale: str
    evidence: list[EvidenceItem]
    raw: dict
    model_id: str
    latency_ms: int
    attempts: int = 1
    repaired: bool = False


async def grade_criterion(
    llm: LLMPort,
    criterion,
    files,
    *,
    model_id: str,
    api_key: str | None = None,
) -> GradeOutcome:
    schema = CriterionJudgment.model_json_schema()
    messages = build_messages(criterion, files, schema=schema)

    start = time.monotonic()
    raw = await llm.complete_json(messages, schema=schema, model_id=model_id, api_key=api_key)
    latency_ms = int((time.monotonic() - start) * 1000)

    repaired = bool(isinstance(raw, dict) and raw.pop("_repaired", False))
    try:
        judgment = CriterionJudgment.model_validate(raw)
    except ValidationError:
        return GradeOutcome(
            verdict=Verdict.ERROR,
            score=None,
            confidence=0.0,
            rationale="LLM returned an unparseable or invalid judgment.",
            evidence=[],
            raw=raw if isinstance(raw, dict) else {"raw": str(raw)},
            model_id=model_id,
            latency_ms=latency_ms,
            repaired=repaired,
        )

    return GradeOutcome(
        verdict=Verdict(judgment.verdict),
        score=judgment.score,
        confidence=judgment.confidence,
        rationale=judgment.rationale,
        evidence=judgment.evidence,
        raw=raw,
        model_id=model_id,
        latency_ms=latency_ms,
        repaired=repaired,
    )
