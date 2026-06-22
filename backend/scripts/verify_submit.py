"""
Verify both submission paths (GitHub + ZIP) end-to-end against a running server.

    python -m scripts.verify_submit [base_url]

Reads OPERATOR_TOKEN from backend/.env. Creates one task, publishes a rubric,
then submits the same task via a GitHub URL and via a ZIP upload, runs a review
for each, and prints whether each completed with a valid decision.
"""

from __future__ import annotations

import asyncio
import io
import os
import sys
import zipfile

import httpx
from dotenv import load_dotenv

load_dotenv(".env")
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
TOKEN = os.environ.get("OPERATOR_TOKEN", "")
H = {"Authorization": f"Bearer {TOKEN}"}

GITHUB_REPO = "https://github.com/octocat/Hello-World"
RUBRIC = {
    "criteria": [
        {"key": "has_readme", "title": "Has a README", "type": "scored", "weight": 50,
         "instructions": "The repository includes a `README` describing the project."},
        {"key": "has_code", "title": "Has source code", "type": "scored", "weight": 50,
         "instructions": "Contains real source `code` — functions / `def` / modules."},
    ],
    "decision_config": {"accept_at": 60, "review_at": 30},
    "prompt_template_version": "grade@v1",
}


def make_zip() -> bytes:
    files = {
        "calc.py": "def add(a, b):\n    return a + b\n",
        "test_calc.py": "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        "README.md": "# Calc\n\nA tiny calculator library with an `add` function.\n",
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


async def _run(c: httpx.AsyncClient, tid: str, sid: str) -> dict:
    r = (await c.post("/api/reviews", json={"task_id": tid, "submission_id": sid})).json()
    rid, status, waited = r["id"], r["status"], 0
    while status in ("queued", "running") and waited < 240:
        await asyncio.sleep(3)
        waited += 3
        r = (await c.get(f"/api/reviews/{rid}")).json()
        status = r["status"]
    return r


def _show(label: str, review: dict) -> bool:
    ok = review.get("status") == "completed" and review.get("decision")
    print(f"\n[{label}] status={review.get('status')} decision={review.get('decision')} "
          f"score={review.get('final_score')}")
    if review.get("error_message"):
        print(f"    error: {review['error_message']}")
    for r in review.get("results", []):
        ev = r["evidence"][0] if r["evidence"] else None
        loc = f" @ {ev['path']}:{ev['start_line']} [{ev['verified']}]" if ev else ""
        print(f"    - {r['criterion_key']:<12} {r['verdict']:<6} score={r['score']}{loc}")
    return bool(ok)


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=120, headers=H) as c:
        h = (await c.get("/api/health")).json()
        print(f"[health] ready={h['ready']} model={h['default_model']} backend={h['llm_backend']}")

        task = (await c.post("/api/tasks", json={"name": "Submission check"})).json()
        tid = task["id"]
        await c.put(f"/api/tasks/{tid}/rubric", json=RUBRIC)
        await c.post(f"/api/tasks/{tid}/rubric/publish")
        print(f"[task] {tid} published")

        # GitHub
        github_ok = False
        try:
            print(f"\n--- GitHub: cloning {GITHUB_REPO} ---")
            gsub = (await c.post(
                "/api/submissions/github", json={"github_url": GITHUB_REPO}
            )).json()
            print(f"    cloned: {gsub.get('file_count')} files")
            github_ok = _show("GITHUB", await _run(c, tid, gsub["id"]))
        except Exception as exc:  # noqa: BLE001
            print(f"[GITHUB] ERROR: {exc}")

        # ZIP
        print("\n--- ZIP: uploading calc.zip ---")
        zsub = (await c.post(
            "/api/submissions/zip",
            files={"file": ("calc.zip", make_zip(), "application/zip")},
        )).json()
        print(f"    uploaded: {zsub.get('file_count')} files")
        zip_ok = _show("ZIP", await _run(c, tid, zsub["id"]))

        print("\n=====================================================")
        print(f"GITHUB submission: {'PASS' if github_ok else 'FAIL'}")
        print(f"ZIP submission:    {'PASS' if zip_ok else 'FAIL'}")
        print("=====================================================")
        return 0 if (github_ok and zip_ok) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
