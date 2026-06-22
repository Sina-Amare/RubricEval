"""Unit tests for the LiteLLM client (mocked acompletion, no network)."""

from __future__ import annotations

from types import SimpleNamespace

import litellm

from app.llm.litellm_client import LiteLLMClient


def _resp(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


async def test_parses_json_directly(monkeypatch):
    async def fake(**kwargs):
        return _resp('{"verdict": "pass", "score": 80}')

    monkeypatch.setattr(litellm, "acompletion", fake)
    out = await LiteLLMClient().complete_json(
        [{"role": "user", "content": "x"}], model_id="m-parse"
    )
    assert out["verdict"] == "pass"
    assert out["score"] == 80


async def test_capability_fallback_drops_response_format(monkeypatch):
    async def fake(**kwargs):
        if "response_format" in kwargs:
            raise Exception("response_format is not supported by this model")
        return _resp('{"verdict": "fail"}')

    monkeypatch.setattr(litellm, "acompletion", fake)
    LiteLLMClient._no_json_mode.discard("m-fallback")
    out = await LiteLLMClient().complete_json(
        [{"role": "user", "content": "x"}], model_id="m-fallback"
    )
    assert out["verdict"] == "fail"
    assert "m-fallback" in LiteLLMClient._no_json_mode


async def test_repair_reask_on_bad_json(monkeypatch):
    async def fake(**kwargs):
        # The primary (json-mode) call returns prose; the repair call returns JSON.
        if "response_format" in kwargs:
            return _resp("Sorry, here is the answer: not json")
        return _resp('{"verdict": "partial", "score": 50}')

    monkeypatch.setattr(litellm, "acompletion", fake)
    LiteLLMClient._no_json_mode.discard("m-repair")
    out = await LiteLLMClient().complete_json(
        [{"role": "user", "content": "x"}], model_id="m-repair"
    )
    assert out["verdict"] == "partial"
    assert out.get("_repaired") is True
