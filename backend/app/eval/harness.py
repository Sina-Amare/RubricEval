"""
Evaluation harness.

Runs the *pure* engine (no DB, no API) over a golden set of cases — each a
rubric + a submission + an expected decision — and reports agreement. This is
what lets you change a prompt or model and *know* whether quality regressed,
instead of guessing. Defaults to the deterministic ``FakeLLM`` so it runs
offline in CI; pass a real client to evaluate against a live model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.api.schemas.task import RubricDraft
from app.engine.evidence import verify_evidence
from app.engine.grader import grade_criterion
from app.engine.policy import GradedCriterion, decide
from app.ingestion.normalize import normalize_items
from app.interfaces.llm import LLMPort
from app.llm.fake import FakeLLM


@dataclass
class CaseResult:
    name: str
    expected: str
    actual: str
    final_score: float
    matched: bool
    verified_evidence: int
    total_evidence: int


@dataclass
class EvalReport:
    cases: list[CaseResult]

    @property
    def agreement(self) -> float:
        if not self.cases:
            return 0.0
        return sum(c.matched for c in self.cases) / len(self.cases)


def _read_files(files_dir: Path) -> list[tuple[str, bytes]]:
    items: list[tuple[str, bytes]] = []
    for path in sorted(files_dir.rglob("*")):
        if path.is_file():
            items.append((str(path.relative_to(files_dir)), path.read_bytes()))
    return items


async def run_eval(
    golden_dir: str | Path,
    llm: LLMPort | None = None,
    model_id: str = "fake",
) -> EvalReport:
    golden = Path(golden_dir)
    llm = llm or FakeLLM()
    cases: list[CaseResult] = []

    for case_dir in sorted(p for p in golden.iterdir() if p.is_dir()):
        spec = json.loads((case_dir / "case.json").read_text())
        draft = RubricDraft(
            criteria=spec["criteria"], decision_config=spec["decision_config"]
        )
        fileset = normalize_items(
            _read_files(case_dir / "files"), "eval", case_dir.name
        )

        graded: list[GradedCriterion] = []
        verified = total = 0
        for crit in draft.criteria:
            outcome = await grade_criterion(
                llm, crit, fileset.files, model_id=model_id
            )
            for ve in verify_evidence(outcome.evidence, fileset):
                total += 1
                if ve.verified.value == "verified":
                    verified += 1
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

        result = decide(
            graded,
            accept_at=draft.decision_config.accept_at,
            review_at=draft.decision_config.review_at,
        )
        cases.append(
            CaseResult(
                name=case_dir.name,
                expected=spec["expected_decision"],
                actual=result.decision.value,
                final_score=result.final_score,
                matched=result.decision.value == spec["expected_decision"],
                verified_evidence=verified,
                total_evidence=total,
            )
        )
    return EvalReport(cases=cases)
