"""Integration tests: real ZIP upload through the API, file browsing, dedup."""

from __future__ import annotations

import io
import zipfile


def make_zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


async def test_zip_submission_flow(client, auth_headers):
    data = make_zip({"src/main.py": "print('hello')\nx = 2\n", "README.md": "# Hi"})

    resp = await client.post(
        "/api/submissions/zip",
        headers=auth_headers,
        files={"file": ("sub.zip", data, "application/zip")},
    )
    assert resp.status_code == 201, resp.text
    sub = resp.json()
    sid = sub["id"]
    assert sub["file_count"] == 2
    paths = {f["path"] for f in sub["files"]}
    assert paths == {"src/main.py", "README.md"}

    # List files
    resp = await client.get(f"/api/submissions/{sid}/files", headers=auth_headers)
    assert resp.status_code == 200
    assert any(f["path"] == "src/main.py" for f in resp.json())

    # Fetch real file content (used by the Monaco viewer)
    resp = await client.get(
        f"/api/submissions/{sid}/files/content",
        params={"path": "src/main.py"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "print('hello')" in body["content"]
    assert body["language"] == "python"

    # Idempotent dedup: identical content -> same submission id
    resp2 = await client.post(
        "/api/submissions/zip",
        headers=auth_headers,
        files={"file": ("sub2.zip", data, "application/zip")},
    )
    assert resp2.json()["id"] == sid


async def test_zip_requires_auth(client):
    data = make_zip({"a.py": "x=1"})
    resp = await client.post(
        "/api/submissions/zip", files={"file": ("a.zip", data, "application/zip")}
    )
    assert resp.status_code == 401


async def test_non_zip_rejected(client, auth_headers):
    resp = await client.post(
        "/api/submissions/zip",
        headers=auth_headers,
        files={"file": ("a.txt", b"not a zip", "text/plain")},
    )
    assert resp.status_code == 400
