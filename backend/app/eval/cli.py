"""
Eval CLI:  python -m app.eval.cli run --golden golden [--real]

Prints a per-case agreement/regression report. Exits non-zero if any case
disagrees with its expected decision, so it can gate CI.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.eval.harness import EvalReport, run_eval


def _print(report: EvalReport) -> None:
    print(f"\n{'CASE':<24} {'EXPECTED':<10} {'ACTUAL':<10} {'SCORE':>7}  EVIDENCE  OK")
    print("-" * 72)
    for c in report.cases:
        ok = "PASS" if c.matched else "FAIL"
        ev = f"{c.verified_evidence}/{c.total_evidence}"
        print(
            f"{c.name:<24} {c.expected:<10} {c.actual:<10} "
            f"{c.final_score:>7.1f}  {ev:>8}  {ok}"
        )
    print("-" * 72)
    print(f"Agreement: {report.agreement:.0%}  ({len(report.cases)} cases)\n")


async def _run(golden: str, real: bool) -> EvalReport:
    if real:
        from app.llm.litellm_client import LiteLLMClient
        from app.settings import get_settings

        return await run_eval(
            golden, llm=LiteLLMClient(), model_id=get_settings().default_model
        )
    return await run_eval(golden)


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.eval.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run", help="Run the eval over a golden set")
    run_p.add_argument("--golden", default="golden")
    run_p.add_argument("--real", action="store_true", help="Use the real LLM, not FakeLLM")
    args = parser.parse_args()

    if args.cmd == "run":
        report = asyncio.run(_run(args.golden, args.real))
        _print(report)
        sys.exit(0 if report.agreement >= 1.0 else 1)


if __name__ == "__main__":
    main()
