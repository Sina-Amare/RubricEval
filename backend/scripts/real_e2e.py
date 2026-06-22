"""
REAL end-to-end driver: real API, real files, real LLM.

Drives a *running* server (started with LLM_BACKEND=litellm and a real
OPENROUTER_API_KEY) exactly like a user would: create task -> publish rubric ->
upload a real ZIP -> run a review -> poll to completion -> print the decision,
per-criterion verdicts, and evidence. No secrets live in this file.

Usage:  python -m scripts.real_e2e [base_url] [operator_token]
"""

from __future__ import annotations

import asyncio
import io
import sys
import zipfile

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8021"
TOKEN = sys.argv[2] if len(sys.argv) > 2 else "e2e-real-token"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

RUBRIC = {
    "criteria": [
        {"key": "has_tests", "title": "Automated tests", "type": "scored",
         "weight": 50,
         "instructions": "The repository includes automated `test` functions."},
        {"key": "implements_add", "title": "Addition function", "type": "scored",
         "weight": 50,
         "instructions": "Implements an `add` function that returns a sum."},
    ],
    "decision_config": {"accept_at": 70, "review_at": 40},
    "prompt_template_version": "grade@v1",
}


def make_zip() -> bytes:
    files = {
        "calc.py": "def add(a, b):\n    \"\"\"Return the sum of a and b.\"\"\"\n    return a + b\n",
        "test_calc.py": "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        "README.md": "# Calculator\n\nA tiny calculator with an `add` function and tests.\n",
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=120, headers=HEADERS) as c:
        health = (await c.get("/api/health")).json()
        print(f"[health] ready={health['ready']} model={health['default_model']} "
              f"backend={health['llm_backend']}")

        task = (await c.post("/api/tasks", json={"name": "Real E2E"})).json()
        tid = task["id"]
        await c.put(f"/api/tasks/{tid}/rubric", json=RUBRIC)
        pub = (await c.post(f"/api/tasks/{tid}/rubric/publish")).json()
        print(f"[rubric] published v{pub['version_number']} hash={pub['content_hash'][:12]}")

        files = {"file": ("calc.zip", make_zip(), "application/zip")}
        sub = (await c.post("/api/submissions/zip", files=files)).json()
        print(f"[submission] {sub['file_count']} files, hash={sub['fileset_hash'][:12]}")

        review = (await c.post(
            "/api/reviews", json={"task_id": tid, "submission_id": sub["id"]}
        )).json()
        rid = review["id"]
        print(f"[review] {rid} queued; waiting for the real model…")

        deadline = 240
        waited = 0
        status = review["status"]
        while status in ("queued", "running") and waited < deadline:
            await asyncio.sleep(3)
            waited += 3
            review = (await c.get(f"/api/reviews/{rid}")).json()
            status = review["status"]
            print(f"    … {waited}s status={status}")

        print("\n==================== REAL RESULT ====================")
        print(f"status     : {review['status']}")
        print(f"model      : {review['model_id']}")
        print(f"decision   : {review['decision']}")
        print(f"score      : {review['final_score']}")
        if review.get("error_message"):
            print(f"error      : {review['error_message']}")
        for r in review.get("results", []):
            ev = r["evidence"][0] if r["evidence"] else None
            loc = f" @ {ev['path']}:{ev['start_line']} [{ev['verified']}]" if ev else ""
            print(f"  - {r['criterion_key']:<16} {r['verdict']:<8} "
                  f"score={r['score']} conf={r['confidence']}{loc}")
        print("=====================================================")

        ok = review["status"] == "completed" and review["decision"] in (
            "accept", "review", "reject"
        )
        print("REAL E2E:", "PASS" if ok else "FAIL")
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
