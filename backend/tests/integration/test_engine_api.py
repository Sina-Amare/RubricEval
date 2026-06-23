"""
Full engine run through the API (offline, deterministic via FakeLLM).

Reviews now run asynchronously via the durable queue; tests drain the queue
with ``drain_jobs`` (the embedded worker isn't running under ASGITransport).
"""

from __future__ import annotations

import io
import zipfile

from app.jobs.worker import drain_jobs


def make_zip() -> bytes:
    files = {
        "main.py": "def add(a, b):\n    return a + b\n",
        "test_main.py": "def test_add():\n    assert add(1, 2) == 3\n",
        "README.md": "# Project\nThis project has documentation.\n",
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


async def make_submission(client, auth_headers) -> str:
    resp = await client.post(
        "/api/submissions/zip",
        headers=auth_headers,
        files={"file": ("s.zip", make_zip(), "application/zip")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def make_task(client, auth_headers, criteria) -> str:
    resp = await client.post("/api/tasks", json={"name": "Eng"}, headers=auth_headers)
    tid = resp.json()["id"]
    draft = {
        "criteria": criteria,
        "decision_config": {"accept_at": 70, "review_at": 50},
        "prompt_template_version": "grade@v1",
    }
    await client.put(f"/api/tasks/{tid}/rubric", json=draft, headers=auth_headers)
    await client.post(f"/api/tasks/{tid}/rubric/publish", headers=auth_headers)
    return tid


async def run_review(client, auth_headers, task_id, submission_id) -> dict:
    resp = await client.post(
        "/api/reviews",
        json={"task_id": task_id, "submission_id": submission_id},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    review_id = resp.json()["id"]
    await drain_jobs()
    resp = await client.get(f"/api/reviews/{review_id}", headers=auth_headers)
    return resp.json()


ACCEPT_CRITERIA = [
    {"key": "has_docs", "title": "Has documentation", "type": "gate",
     "gate_policy": "must_pass", "instructions": "Project includes `documentation`."},
    {"key": "has_tests", "title": "Has tests", "type": "scored", "weight": 60,
     "instructions": "Includes automated `test` functions."},
    {"key": "has_add", "title": "Implements add", "type": "scored", "weight": 40,
     "instructions": "Implements an `add` function."},
]


async def test_review_accept_with_verified_evidence(client, auth_headers):
    sid = await make_submission(client, auth_headers)
    tid = await make_task(client, auth_headers, ACCEPT_CRITERIA)
    review = await run_review(client, auth_headers, tid, sid)

    assert review["status"] == "completed"
    assert review["decision"] == "accept"
    assert review["final_score"] == 85.0
    assert review["gate_failed"] is False
    assert review["prompt_template_version"] == "grade@v2"
    assert len(review["rubric_content_hash"]) == 64
    assert review["model_id"] and review["engine_version"]

    results = {r["criterion_key"]: r for r in review["results"]}
    assert set(results) == {"has_docs", "has_tests", "has_add"}
    ev = results["has_tests"]["evidence"][0]
    assert ev["verified"] == "verified"
    assert ev["path"] == "test_main.py"
    assert ev["start_line"] >= 1


async def test_review_reject_on_gate_failure(client, auth_headers):
    sid = await make_submission(client, auth_headers)
    criteria = [
        {"key": "has_k8s", "title": "Kubernetes", "type": "gate",
         "gate_policy": "must_pass", "instructions": "Must include `kubernetes`."},
        {"key": "has_add", "title": "Implements add", "type": "scored", "weight": 100,
         "instructions": "Implements an `add` function."},
    ]
    tid = await make_task(client, auth_headers, criteria)
    review = await run_review(client, auth_headers, tid, sid)
    assert review["decision"] == "reject"
    assert review["gate_failed"] is True


async def test_review_idempotent(client, auth_headers):
    sid = await make_submission(client, auth_headers)
    tid = await make_task(client, auth_headers, ACCEPT_CRITERIA)
    r1 = await client.post(
        "/api/reviews", json={"task_id": tid, "submission_id": sid}, headers=auth_headers
    )
    r2 = await client.post(
        "/api/reviews", json={"task_id": tid, "submission_id": sid}, headers=auth_headers
    )
    assert r1.json()["id"] == r2.json()["id"]


async def test_review_requires_published_rubric(client, auth_headers):
    sid = await make_submission(client, auth_headers)
    resp = await client.post("/api/tasks", json={"name": "NoPub"}, headers=auth_headers)
    tid = resp.json()["id"]
    resp = await client.post(
        "/api/reviews", json={"task_id": tid, "submission_id": sid}, headers=auth_headers
    )
    assert resp.status_code == 400
