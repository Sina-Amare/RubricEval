"""
LiteLLM-backed LLM client — provider-agnostic, BYOK, with key rotation.

Works across OpenRouter, Groq, and Google Gemini (the provider is inferred from
the model id prefix). Designed for weak/free models that may not support
tool-calling or JSON mode: we embed the schema in the prompt, request
``response_format`` json when available (falling back if rejected), parse with
``json_recovery``, and do a bounded repair re-ask. Comma-separated keys are
rotated round-robin and advanced on rate-limit to spread quota.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import litellm

from app.core.exceptions import LLMError, RateLimitError
from app.interfaces.llm import LLMPort
from app.settings import Settings, get_settings
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


def _friendly_error(exc: Exception) -> str:
    name = type(exc).__name__
    msg = str(exc).lower()
    is_auth = isinstance(exc, getattr(litellm, "AuthenticationError", ()))
    if is_auth or "auth" in msg or "api key" in msg or "401" in msg:
        return "Authentication failed — check the API key."
    if _is_rate_limit(exc):
        return "Rate limited — the key works but is currently throttled."
    not_found = isinstance(exc, getattr(litellm, "NotFoundError", ()))
    if not_found or "not found" in msg or "404" in msg or "does not exist" in msg:
        return "Model not found or not accessible with this key."
    if isinstance(exc, getattr(litellm, "ContextWindowExceededError", ())):
        return "Context window exceeded."
    if isinstance(exc, getattr(litellm, "Timeout", ())) or "timeout" in msg or "timed out" in msg:
        return "Request timed out."
    if isinstance(exc, getattr(litellm, "APIConnectionError", ())) or "connection" in msg:
        return "Could not reach the provider."
    return f"{name}: {str(exc)[:160]}"


def _provider_of(model_id: str) -> str:
    m = (model_id or "").lower()
    if m.startswith("groq/"):
        return "groq"
    if m.startswith(("gemini/", "google/", "vertex_ai/")):
        return "gemini"
    return "openrouter"


def _key_list(model_id: str, api_key: Optional[str], settings: Settings) -> list[Optional[str]]:
    """Keys to try for this call: explicit BYOK (parsed), else provider env keys."""
    raw = api_key
    if not raw:
        raw = {
            "groq": settings.groq_api_key,
            "gemini": settings.google_api_key,
            "openrouter": settings.openrouter_api_key,
        }.get(_provider_of(model_id))
    keys = [k.strip() for k in (raw or "").split(",") if k.strip()]
    return keys or [None]


def _model_chain(model: str, settings: Settings) -> list[str]:
    """Primary model first, then configured fallbacks (deduped, primary kept)."""
    chain = [model]
    for m in (settings.fallback_model or "").split(","):
        m = m.strip()
        if m and m not in chain and _key_list(m, None, settings) != [None]:
            chain.append(m)  # only include fallbacks we actually have a key for
    return chain


class LiteLLMClient(LLMPort):
    _no_json_mode: set[str] = set()
    _counter: int = 0

    @classmethod
    def _start_index(cls) -> int:
        cls._counter += 1
        return cls._counter

    async def ping(
        self, *, model_id: str | None = None, api_key: str | None = None
    ) -> dict:
        import time

        settings = get_settings()
        model = model_id or settings.default_model
        key = _key_list(model, api_key, settings)[0]
        start = time.monotonic()
        try:
            await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                api_key=key,
                max_tokens=1,
                timeout=20,
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
                "message": _friendly_error(exc),
            }

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

        # BYOK (explicit key) targets one specific model; the env-key path may
        # fall back across providers to dodge a single provider's rate limit.
        chain = [model] if api_key else _model_chain(model, settings)
        last_exc: Exception | None = None
        for i, m in enumerate(chain):
            try:
                return await self._complete_one(m, messages, api_key, settings)
            except LLMError as exc:  # includes RateLimitError (subclass)
                last_exc = exc
                if i + 1 < len(chain):
                    logger.warning(f"model {m} failed ({exc}); trying {chain[i + 1]}")
        raise last_exc or LLMError("All models in the chain failed")

    async def _complete_one(
        self,
        model: str,
        messages: list[dict[str, str]],
        api_key: Optional[str],
        settings: Settings,
    ) -> dict[str, Any]:
        keys = _key_list(model, api_key, settings)
        start_idx = self._start_index()
        max_attempts = max(settings.llm_max_attempts, len(keys))
        last_exc: Exception | None = None

        for attempt in range(max_attempts):
            key = keys[(start_idx + attempt) % len(keys)]  # rotate per attempt
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

            except LLMError:
                raise
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if _rejects_response_format(exc) and model not in self._no_json_mode:
                    logger.warning(f"{model} rejects response_format; disabling it")
                    self._no_json_mode.add(model)
                    continue
                if _is_rate_limit(exc):
                    # Rotate to the next key (handled by attempt+1 indexing) + backoff.
                    retry_after = getattr(exc, "retry_after", None) or 2 ** min(attempt, 4)
                    if attempt < max_attempts - 1:
                        logger.warning("rate limited; rotating key + backing off")
                        await asyncio.sleep(min(float(retry_after), 20.0))
                        continue
                    raise RateLimitError(str(exc), retry_after=retry_after) from exc
                if _is_transient(exc) and attempt < max_attempts - 1:
                    await asyncio.sleep(2 ** min(attempt, 4))
                    continue
                raise LLMError(f"{type(exc).__name__}: {str(exc)[:200]}") from exc

        raise LLMError(f"LLM failed after {max_attempts} attempts: {last_exc}")

    async def _call(
        self, model: str, messages: list[dict], key: str | None, settings, *, use_json: bool
    ) -> str:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": settings.llm_temperature,
            "timeout": settings.llm_call_timeout,
            "max_tokens": settings.llm_max_output_tokens,
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
                    "corrected JSON object — no prose, no markdown fences, no trailing text."
                ),
            },
        ]
        try:
            text = await self._call(model, repair_messages, key, settings, use_json=False)
            return extract_json(text)
        except Exception:  # noqa: BLE001
            return None
