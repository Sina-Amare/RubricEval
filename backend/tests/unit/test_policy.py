"""Exhaustive unit tests for the deterministic decision policy."""

from __future__ import annotations

from app.core.enums import CriterionType, Decision, GatePolicy, Verdict
from app.engine.policy import GradedCriterion, decide


def scored(key, verdict, score, weight):
    return GradedCriterion(key, CriterionType.SCORED, verdict, score, weight)


def gate(key, verdict, policy=GatePolicy.MUST_PASS):
    return GradedCriterion(key, CriterionType.GATE, verdict, None, 0.0, policy)


def test_weighted_mean():
    res = decide(
        [scored("a", Verdict.PASS, 80, 60), scored("b", Verdict.PASS, 50, 40)],
        accept_at=70, review_at=50,
    )
    assert res.final_score == 68.0  # (80*60 + 50*40)/100
    assert res.decision == Decision.REVIEW  # 68 in [50,70)


def test_accept_threshold_inclusive():
    res = decide([scored("a", Verdict.PASS, 70, 100)], accept_at=70, review_at=50)
    assert res.decision == Decision.ACCEPT


def test_review_threshold_inclusive():
    res = decide([scored("a", Verdict.PARTIAL, 50, 100)], accept_at=70, review_at=50)
    assert res.decision == Decision.REVIEW


def test_below_review_is_reject():
    res = decide([scored("a", Verdict.FAIL, 49, 100)], accept_at=70, review_at=50)
    assert res.decision == Decision.REJECT


def test_must_pass_gate_failure_forces_reject_even_with_high_scores():
    res = decide(
        [gate("g", Verdict.FAIL), scored("a", Verdict.PASS, 100, 100)],
        accept_at=70, review_at=50,
    )
    assert res.decision == Decision.REJECT
    assert res.gate_failed is True


def test_force_reject_gate_partial_also_fails():
    res = decide(
        [gate("kill", Verdict.PARTIAL, GatePolicy.FORCE_REJECT),
         scored("a", Verdict.PASS, 100, 100)],
        accept_at=70, review_at=50,
    )
    assert res.decision == Decision.REJECT
    assert res.gate_failed is True


def test_gate_error_forces_review_never_accept():
    res = decide(
        [gate("g", Verdict.ERROR), scored("a", Verdict.PASS, 100, 100)],
        accept_at=70, review_at=50,
    )
    assert res.decision == Decision.REVIEW
    assert res.gate_failed is False


def test_scored_error_counts_as_zero():
    res = decide(
        [scored("a", Verdict.ERROR, None, 50), scored("b", Verdict.PASS, 100, 50)],
        accept_at=70, review_at=50,
    )
    assert res.final_score == 50.0  # (0*50 + 100*50)/100
    assert res.decision == Decision.REVIEW


def test_passing_gate_does_not_block():
    res = decide(
        [gate("g", Verdict.PASS), scored("a", Verdict.PASS, 90, 100)],
        accept_at=70, review_at=50,
    )
    assert res.decision == Decision.ACCEPT
    assert res.gate_failed is False


def test_breakdown_shape():
    res = decide([scored("a", Verdict.PASS, 80, 100)], accept_at=70, review_at=50)
    b = res.breakdown
    assert b["final_score"] == 80.0
    assert b["thresholds"] == {"accept_at": 70, "review_at": 50}
    assert b["contributions"][0]["key"] == "a"
    assert b["contributions"][0]["contribution"] == 8000.0


def test_no_scored_criteria_only_gates():
    res = decide([gate("g", Verdict.PASS)], accept_at=70, review_at=50)
    # No scored weight -> final 0 -> but gate passes; 0 < review_at -> REJECT
    assert res.final_score == 0.0
    assert res.decision == Decision.REJECT
