"""DTOs for reviews, criterion results, and evidence."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.core.enums import Decision, EvidenceVerification, ReviewStatus, Verdict


class CreateReviewIn(BaseModel):
    task_id: str
    submission_id: str


class EvidenceOut(BaseModel):
    path: str
    start_line: int
    end_line: int
    quote: str
    verified: EvidenceVerification


class CriterionResultOut(BaseModel):
    criterion_id: str
    criterion_key: str
    verdict: Verdict
    score: Optional[float]
    confidence: float
    rationale: str = ""
    latency_ms: int
    repaired: bool
    evidence: list[EvidenceOut]


class ReviewOut(BaseModel):
    id: str
    task_id: str
    rubric_version_id: str
    submission_id: str
    status: ReviewStatus
    decision: Optional[Decision]
    final_score: Optional[float]
    gate_failed: bool
    decision_breakdown: Optional[dict]
    model_id: str
    prompt_template_version: str
    rubric_content_hash: str
    engine_version: str
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    results: list[CriterionResultOut]


class ReviewSummaryOut(BaseModel):
    id: str
    task_id: str
    submission_id: str
    status: ReviewStatus
    decision: Optional[Decision]
    final_score: Optional[float]
    created_at: datetime
    completed_at: Optional[datetime]
