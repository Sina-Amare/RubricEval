"""LLM adapters + factory."""

from __future__ import annotations

from app.interfaces.llm import LLMPort
from app.settings import get_settings


def get_llm() -> LLMPort:
    """Select the LLM backend from settings (``fake`` for offline/tests)."""
    settings = get_settings()
    if settings.llm_backend == "fake":
        from app.llm.fake import FakeLLM

        return FakeLLM()
    from app.llm.litellm_client import LiteLLMClient

    return LiteLLMClient()
