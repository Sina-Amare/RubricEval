"""Integration tests for the tasks + rubric API (real HTTP, real SQLite DB)."""

from __future__ import annotations


def _draft(quality_weight: float = 60.0) -> dict:
    return {
        "criteria": [
            {
                "key": "no_plagiarism",
                "title": "No plagiarism",
                "type": "gate",
                "gate_policy": "force_reject",
            },
            {"key": "quality", "title": "Code quality", "type": "scored",
             "weight": quality_weight},
            {"key": "tests", "title": "Has tests", "type": "scored", "weight": 40.0},
        ],
        "decision_config": {"accept_at": 70, "review_at": 50},
        "prompt_template_version": "grade@v1",
    }


async def test_requires_auth(client):
    resp = await client.post("/api/tasks", json={"name": "X"})
    assert resp.status_code == 401


async def test_task_lifecycle_and_versioning(client, auth_headers):
    # Create
    resp = await client.post("/api/tasks", json={"name": "Backend Go"}, headers=auth_headers)
    assert resp.status_code == 201
    task = resp.json()
    tid = task["id"]

    # Save draft
    resp = await client.put(f"/api/tasks/{tid}/rubric", json=_draft(), headers=auth_headers)
    assert resp.status_code == 200

    # Publish v1
    resp = await client.post(f"/api/tasks/{tid}/rubric/publish", headers=auth_headers)
    assert resp.status_code == 200
    pub1 = resp.json()
    assert pub1["version_number"] == 1
    assert len(pub1["content_hash"]) == 64

    # Change the draft and publish v2
    resp = await client.put(
        f"/api/tasks/{tid}/rubric", json=_draft(61.0), headers=auth_headers
    )
    assert resp.status_code == 200
    resp = await client.post(f"/api/tasks/{tid}/rubric/publish", headers=auth_headers)
    pub2 = resp.json()
    assert pub2["version_number"] == 2
    assert pub2["content_hash"] != pub1["content_hash"]  # content changed -> hash changed

    # v1 is immutable: re-reading it returns the original hash + criteria
    resp = await client.get(
        f"/api/tasks/{tid}/rubric/versions/{pub1['rubric_version_id']}", headers=auth_headers
    )
    assert resp.status_code == 200
    v1 = resp.json()
    assert v1["content_hash"] == pub1["content_hash"]
    assert {c["key"] for c in v1["criteria"]} == {"no_plagiarism", "quality", "tests"}
    quality = next(c for c in v1["criteria"] if c["key"] == "quality")
    assert quality["weight"] == 60.0  # NOT changed by the later v2 publish

    # Task now points at v2
    resp = await client.get(f"/api/tasks/{tid}", headers=auth_headers)
    assert resp.json()["current_version_number"] == 2

    # Listing versions returns both, newest first
    resp = await client.get(f"/api/tasks/{tid}/rubric/versions", headers=auth_headers)
    versions = resp.json()
    assert [v["version_number"] for v in versions] == [2, 1]


async def test_publish_empty_rubric_rejected(client, auth_headers):
    resp = await client.post("/api/tasks", json={"name": "Empty"}, headers=auth_headers)
    tid = resp.json()["id"]
    resp = await client.post(f"/api/tasks/{tid}/rubric/publish", headers=auth_headers)
    assert resp.status_code == 400
