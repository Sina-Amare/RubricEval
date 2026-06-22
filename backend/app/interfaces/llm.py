"""LLM port: produce a JSON object for a prompt, provider-agnostic."""

from __future__ import annotations

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
