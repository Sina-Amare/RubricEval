"""
LiteLLM-backed LLM client (provider-agnostic, BYOK).

Designed for weak/free models that may not support tool-calling or even JSON
mode: we always embed the schema in the prompt, request ``response_format`` json
when available (falling back transparently if the model rejects it), then parse
with ``json_recovery`` and do one bounded repair re-ask. Errors are mapped to
retryable (rate-limit/timeout/transient) vs terminal.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import litellm

from app.core.exceptions import LLMError, RateLimitError
from app.interfaces.llm import LLMPort
from app.settings import get_settings
from app.utils.json_recovery import extract_json
from app.utils.logger import setup_logger

logger = setup_logger("app.llm.litellm")

litellm.suppress_debug_info = True


def _is_rate_limit(exc: Exception) -> bool:
    if isinstance(exc, getattr(litellm, "RateLimitError", ())):
        return True
    return getattr(exc, "status_code", None) == 429


def _is_transient(exc: Exception) -> bool:
    transient = tuple(
        t
        for t in (
            getattr(litellm, "Timeout", None),
            getattr(litellm, "APIConnectionError", None),
            getattr(litellm, "ServiceUnavailableError", None),
            getattr(litellm, "InternalServerError", None),
        )
        if t is not None
    )
    return isinstance(exc, transient)


def _rejects_response_format(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "response_format" in msg or ("json" in msg and "support" in msg)


class LiteLLMClient(LLMPort):
    # Models observed to reject response_format -> stop sending it.
    _no_json_mode: set[str] = set()

    async def complete_json(
        self,
        messages: list[dict[str, str]],
        *,
        schema: Optional[dict[str, Any]] = None,
        model_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> dict[str, Any]:
        settings = get_settings()
        model = model_id or settings.default_model
        key = api_key or settings.openrouter_api_key
        max_attempts = settings.llm_max_attempts
        last_exc: Exception | None = None

        for attempt in range(max_attempts):
            try:
                text = await self._call(model, messages, key, settings, use_json=True)
                data = extract_json(text)
                if data is not None:
                    return data
                repaired = await self._repair(model, messages, text, key, settings)
                if repaired is not None:
                    repaired["_repaired"] = True
                    return repaired
                raise LLMError("Model output was not valid JSON after repair")

            except RateLimitError:
                raise
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if _rejects_response_format(exc) and model not in self._no_json_mode:
                    logger.warning(f"{model} rejects response_format; disabling it")
                    self._no_json_mode.add(model)
                    continue
                if _is_rate_limit(exc):
                    retry_after = getattr(exc, "retry_after", None) or 2 ** attempt
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(min(float(retry_after), 30.0))
                        continue
                    raise RateLimitError(str(exc), retry_after=retry_after) from exc
                if _is_transient(exc) and attempt < max_attempts - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise LLMError(f"{type(exc).__name__}: {exc}") from exc

        raise LLMError(f"LLM failed after {max_attempts} attempts: {last_exc}")

    async def _call(
        self, model: str, messages: list[dict], key: str | None, settings, *, use_json: bool
    ) -> str:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": settings.llm_temperature,
            "timeout": settings.llm_call_timeout,
            "max_tokens": 4000,
        }
        if key:
            kwargs["api_key"] = key
        if use_json and model not in self._no_json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = await litellm.acompletion(**kwargs)
        return response.choices[0].message.content or ""

    async def _repair(
        self, model: str, messages: list[dict], bad_output: str, key: str | None, settings
    ) -> Optional[dict]:
        repair_messages = [
            *messages,
            {"role": "assistant", "content": bad_output[:4000]},
            {
                "role": "user",
                "content": (
                    "Your previous response was not valid JSON. Reply with ONLY the "
                    "corrected JSON object — no prose, no markdown fences."
                ),
            },
        ]
        try:
            text = await self._call(model, repair_messages, key, settings, use_json=False)
            return extract_json(text)
        except Exception:  # noqa: BLE001
            return None
