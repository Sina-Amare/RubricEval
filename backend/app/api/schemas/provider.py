"""DTOs for BYOK provider configuration (keys never returned)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProviderConfigIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider: str = "openrouter"
    model_id: str = Field(min_length=1, max_length=200)
    api_key: str = Field(min_length=1)
    is_default: bool = False


class ProviderTestIn(BaseModel):
    provider: str = "openrouter"
    model_id: str = Field(min_length=1, max_length=200)
    api_key: str = Field(min_length=1)


class ProviderTestResult(BaseModel):
    ok: bool
    latency_ms: int
    message: str
    model_id: str | None = None


class ProviderConfigOut(BaseModel):
    id: str
    name: str
    provider: str
    model_id: str
    key_fingerprint: str
    is_default: bool
    created_at: datetime
