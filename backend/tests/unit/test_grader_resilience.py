"""A flaky/failing LLM on one criterion must NOT crash the whole review."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Optional

from app.core.enums import CriterionType, Verdict
from app.engine.grader import grade_criterion
from app.interfaces.llm import LLMPort


class _RaisingLLM(LLMPort):
    async def complete_json(
        self,
        messages: list[dict[str, str]],
        *,
        schema: Optional[dict[str, Any]] = None,
        model_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> dict[str, Any]:
        raise RuntimeError("Model output was not valid JSON after repair")


def _criterion():
    return SimpleNamespace(
        key="error_handling",
        title="Error handling",
        instructions="Uses `try`/`except`.",
        type=CriterionType.SCORED,
        weight=30,
    )


async def test_grade_criterion_returns_error_not_raise():
    outcome = await grade_criterion(_RaisingLLM(), _criterion(), [], model_id="m")
    assert outcome.verdict == Verdict.ERROR
    assert outcome.score is None
    assert "failed" in outcome.rationale.lower()
