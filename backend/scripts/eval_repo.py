"""Evaluate a GitHub repo against a task and print the full result.

    python -m scripts.eval_repo <github_url> [task_name] [base_url]
"""

from __future__ import annotations

import asyncio
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv(".env")
URL = sys.argv[1]
TASK_NAME = sys.argv[2] if len(sys.argv) > 2 else "Senior Python Service"
BASE = sys.argv[3] if len(sys.argv) > 3 else "http://localhost:8000"
H = {"Authorization": f"Bearer {os.environ.get('OPERATOR_TOKEN', '')}"}


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=60, headers=H) as c:
        tasks = (await c.get("/api/tasks")).json()
        task = next((t for t in tasks if t["name"] == TASK_NAME), None)
        if task is None:
            print(f"task '{TASK_NAME}' not found; have: {[t['name'] for t in tasks]}")
            return 1
        tid = task["id"]
        print(f"task: {TASK_NAME} ({tid})  repo: {URL}")

        # Re-publish so this run gets a fresh review (new rubric version).
        await c.post(f"/api/tasks/{tid}/rubric/publish")

        sub = (await c.post("/api/submissions/github", json={"github_url": URL})).json()
        if "id" not in sub:
            print(f"ingest failed: {sub}")
            return 1
        print(f"ingested: {sub['file_count']} files, {sub['total_bytes'] // 1024} KB")

        r = (await c.post("/api/reviews", json={"task_id": tid, "submission_id": sub["id"]})).json()
        rid, status, waited = r["id"], r["status"], 0
        while status in ("queued", "running") and waited < 300:
            await asyncio.sleep(4)
            waited += 4
            r = (await c.get(f"/api/reviews/{rid}")).json()
            if r["status"] != status:
                print(f"  [{waited}s] {r['status']}")
            status = r["status"]

        print("\n==================== RESULT ====================")
        print(f"status   : {r['status']}")
        print(f"decision : {r.get('decision')}   score: {r.get('final_score')}")
        if r.get("error_message"):
            print(f"error    : {r['error_message']}")
        for res in r.get("results", []):
            ev = res["evidence"][0] if res["evidence"] else None
            loc = f" @ {ev['path']}:{ev['start_line']} [{ev['verified']}]" if ev else ""
            print(f"  - {res['criterion_key']:<16} {res['verdict']:<7} "
                  f"score={res['score']}{loc}")
        print("================================================")
        # Success = the review COMPLETED (individual criterion errors are tolerated).
        return 0 if r["status"] == "completed" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
