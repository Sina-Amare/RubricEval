"""Durable jobs, the review-event log, SSE replay, and orphan reclaim."""

from __future__ import annotations

import asyncio
import io
import zipfile
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.enums import JobState
from app.db.base import get_sessionmaker
from app.db.models import Job
from app.jobs import queue as q
from app.jobs.worker import drain_jobs

CRITERIA = [
    {"key": "has_tests", "title": "Has tests", "type": "scored", "weight": 60,
     "instructions": "Includes automated `test` functions."},
    {"key": "has_add", "title": "Implements add", "type": "scored", "weight": 40,
     "instructions": "Implements an `add` function."},
]


def _zip() -> bytes:
    files = {
        "main.py": "def add(a, b):\n    return a + b\n",
        "test_main.py": "def test_add():\n    assert add(1, 2) == 3\n",
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


async def _enqueue_review(client, auth_headers) -> str:
    resp = await client.post(
        "/api/submissions/zip",
        headers=auth_headers,
        files={"file": ("s.zip", _zip(), "application/zip")},
    )
    sid = resp.json()["id"]
    resp = await client.post("/api/tasks", json={"name": "J"}, headers=auth_headers)
    tid = resp.json()["id"]
    draft = {"criteria": CRITERIA, "decision_config": {"accept_at": 70, "review_at": 50}}
    await client.put(f"/api/tasks/{tid}/rubric", json=draft, headers=auth_headers)
    await client.post(f"/api/tasks/{tid}/rubric/publish", headers=auth_headers)
    resp = await client.post(
        "/api/reviews",
        json={"task_id": tid, "submission_id": sid},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "queued"  # async: not run inline
    assert body["decision"] is None
    return body["id"]


async def test_async_lifecycle_and_event_log(client, auth_headers):
    rid = await _enqueue_review(client, auth_headers)
    assert await drain_jobs() >= 1

    resp = await client.get(f"/api/reviews/{rid}", headers=auth_headers)
    assert resp.json()["status"] == "completed"

    resp = await client.get(f"/api/reviews/{rid}/events", headers=auth_headers)
    types = [e["type"] for e in resp.json()]
    assert types[0] == "review_started"
    assert "criterion_completed" in types
    assert "decision_computed" in types
    assert types[-1] == "review_completed"


async def test_sse_replay_after_completion(client, auth_headers):
    rid = await _enqueue_review(client, auth_headers)
    await drain_jobs()

    async def _read() -> str:
        body = ""
        async with client.stream(
            "GET", f"/api/reviews/{rid}/stream", headers=auth_headers
        ) as resp:
            assert resp.status_code == 200
            async for chunk in resp.aiter_text():
                body += chunk
                if "review_completed" in body:
                    return body
        return body

    body = await asyncio.wait_for(_read(), timeout=30)
    assert "event: review_started" in body
    assert "event: review_completed" in body


async def test_orphan_job_is_reclaimed(client, auth_headers):
    rid = await _enqueue_review(client, auth_headers)
    sm = get_sessionmaker()

    async with sm() as session:
        job = await session.scalar(select(Job).where(Job.review_id == rid))
        job.state = JobState.LEASED
        job.leased_until = datetime.now(timezone.utc) - timedelta(minutes=5)
        await session.commit()

    async with sm() as session:
        assert await q.reclaim_orphans(session) >= 1

    assert await drain_jobs() >= 1
    resp = await client.get(f"/api/reviews/{rid}", headers=auth_headers)
    assert resp.json()["status"] == "completed"
