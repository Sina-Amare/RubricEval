"""The eval harness should fully agree with the golden set (offline FakeLLM)."""

from __future__ import annotations

from pathlib import Path

from app.eval.harness import run_eval

GOLDEN = Path(__file__).resolve().parents[2] / "golden"


async def test_golden_agreement_is_total():
    report = await run_eval(GOLDEN)
    assert {c.name for c in report.cases} == {"case_accept", "case_reject"}
    assert report.agreement == 1.0


async def test_accept_case_has_verified_evidence():
    report = await run_eval(GOLDEN)
    accept = next(c for c in report.cases if c.name == "case_accept")
    assert accept.actual == "accept"
    assert accept.verified_evidence > 0
