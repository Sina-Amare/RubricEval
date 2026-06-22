"""Integration tests for BYOK provider configs (real API, encryption, resolve)."""

from __future__ import annotations

from app.db.base import get_sessionmaker
from app.services.provider_configs import resolve_credentials


async def test_requires_auth(client):
    resp = await client.post("/api/provider-configs", json={})
    assert resp.status_code == 401


async def test_create_list_resolve(client, auth_headers):
    resp = await client.post(
        "/api/provider-configs",
        headers=auth_headers,
        json={
            "name": "OpenRouter",
            "provider": "openrouter",
            "model_id": "openrouter/openai/gpt-oss-120b:free",
            "api_key": "sk-or-secret-9999",
            "is_default": True,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "api_key" not in body  # key never returned
    assert body["key_fingerprint"].endswith("9999")
    assert body["is_default"] is True

    resp = await client.get("/api/provider-configs", headers=auth_headers)
    configs = resp.json()
    assert len(configs) == 1
    assert "api_key" not in configs[0]

    # The default config drives credential resolution (key decrypts correctly).
    async with get_sessionmaker()() as session:
        model, key = await resolve_credentials(session)
    assert model == "openrouter/openai/gpt-oss-120b:free"
    assert key == "sk-or-secret-9999"


async def test_set_default_switches(client, auth_headers):
    async def make(name, default):
        resp = await client.post(
            "/api/provider-configs",
            headers=auth_headers,
            json={"name": name, "model_id": f"m/{name}", "api_key": f"sk-{name}",
                  "is_default": default},
        )
        return resp.json()["id"]

    await make("a", True)
    bid = await make("b", False)

    resp = await client.post(f"/api/provider-configs/{bid}/default", headers=auth_headers)
    assert resp.status_code == 200
    async with get_sessionmaker()() as session:
        model, _ = await resolve_credentials(session)
    assert model == "m/b"
