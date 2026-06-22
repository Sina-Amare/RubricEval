"""Pydantic schemas for per-criterion grading (the LLM's required output)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    quote: str = ""


class CriterionJudgment(BaseModel):
    """The structured judgment the grader requires for each criterion."""

    verdict: Literal["pass", "fail", "partial"]
    score: float | None = Field(default=None, ge=0, le=100)
    confidence: float = Field(default=0.5, ge=0, le=1)
    rationale: str = ""
    evidence: list[EvidenceItem] = Field(default_factory=list)
