"""LLM port: produce a JSON object for a prompt, provider-agnostic."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Optional


class LLMPort(ABC):
    """A minimal interface the grader depends on.

    Implementations return a best-effort-parsed ``dict`` (the engine validates
    it against a Pydantic schema). They must NOT rely on native tool-calling.
    """

    @abstractmethod
    async def complete_json(
        self,
        messages: list[dict[str, str]],
        *,
        schema: Optional[dict[str, Any]] = None,
        model_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> dict[str, Any]:
        ...

    async def ping(
        self, *, model_id: Optional[str] = None, api_key: Optional[str] = None
    ) -> dict[str, Any]:
        """Lightweight connection check. Returns {ok, latency_ms, message} and
        never raises (errors are reported in the result). Default uses a tiny
        completion; real providers override with friendlier error mapping."""
        start = time.monotonic()
        try:
            await self.complete_json(
                [{"role": "user", "content": 'Return JSON {"ok": true}.'}],
                schema={"type": "object"},
                model_id=model_id,
                api_key=api_key,
            )
            return {
                "ok": True,
                "latency_ms": int((time.monotonic() - start) * 1000),
                "message": "Connection OK",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "latency_ms": int((time.monotonic() - start) * 1000),
                "message": str(exc)[:200],
            }
