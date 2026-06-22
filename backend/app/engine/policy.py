"""
The deterministic decision policy.

This is the ONLY place a final decision is made. It is a pure function of the
graded criteria plus the rubric's thresholds — no LLM, no I/O — so it is fully
unit-testable and reproducible. The LLM never decides accept/reject.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.core.enums import CriterionType, Decision, GatePolicy, Verdict


@dataclass
class GradedCriterion:
    key: str
    type: CriterionType
    verdict: Verdict
    score: Optional[float]
    weight: float
    gate_policy: Optional[GatePolicy] = None


@dataclass
class DecisionResult:
    decision: Decision
    final_score: float
    gate_failed: bool
    breakdown: dict = field(default_factory=dict)


def decide(
    graded: list[GradedCriterion], *, accept_at: float, review_at: float
) -> DecisionResult:
    gates = [g for g in graded if g.type == CriterionType.GATE]
    scored = [g for g in graded if g.type == CriterionType.SCORED]

    # A gate fails when it is not passed (fail/partial). Both must_pass and
    # force_reject gates reject on non-pass; force_reject is the kill-switch.
    hard_gate_failures = [
        {"key": g.key, "policy": g.gate_policy.value if g.gate_policy else None,
         "verdict": g.verdict.value}
        for g in gates
        if g.verdict in (Verdict.FAIL, Verdict.PARTIAL)
    ]
    # A gate whose grading errored cannot certify the submission -> force REVIEW.
    gate_errored = any(g.verdict == Verdict.ERROR for g in gates)

    # Weighted mean over scored criteria; an errored scored criterion counts 0.
    total_weight = sum(g.weight for g in scored)
    contributions = []
    weighted_sum = 0.0
    for g in scored:
        score = g.score if (g.score is not None and g.verdict != Verdict.ERROR) else 0.0
        contribution = score * g.weight
        weighted_sum += contribution
        contributions.append(
            {
                "key": g.key,
                "verdict": g.verdict.value,
                "score": score,
                "weight": g.weight,
                "contribution": contribution,
            }
        )
    final_score = (weighted_sum / total_weight) if total_weight > 0 else 0.0

    if hard_gate_failures:
        decision = Decision.REJECT
        gate_failed = True
    elif gate_errored:
        decision = Decision.REVIEW
        gate_failed = False
    elif final_score >= accept_at:
        decision = Decision.ACCEPT
        gate_failed = False
    elif final_score >= review_at:
        decision = Decision.REVIEW
        gate_failed = False
    else:
        decision = Decision.REJECT
        gate_failed = False

    breakdown = {
        "final_score": round(final_score, 2),
        "thresholds": {"accept_at": accept_at, "review_at": review_at},
        "total_weight": total_weight,
        "contributions": contributions,
        "gates": [
            {"key": g.key, "policy": g.gate_policy.value if g.gate_policy else None,
             "verdict": g.verdict.value}
            for g in gates
        ],
        "gate_failures": hard_gate_failures,
        "gate_errored": gate_errored,
    }
    return DecisionResult(
        decision=decision,
        final_score=round(final_score, 2),
        gate_failed=gate_failed,
        breakdown=breakdown,
    )
