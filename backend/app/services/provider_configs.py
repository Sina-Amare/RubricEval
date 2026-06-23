"""Provider-config service: create with encryption, resolve credentials."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ProviderConfig
from app.db.repositories.provider_configs import ProviderConfigRepository
from app.security.crypto import decrypt, encrypt, fingerprint
from app.settings import get_settings
from app.utils.logger import setup_logger

logger = setup_logger("app.services.provider")


async def create_provider_config(
    session: AsyncSession,
    *,
    name: str,
    provider: str,
    model_id: str,
    api_key: str,
    is_default: bool,
) -> ProviderConfig:
    repo = ProviderConfigRepository(session)
    if is_default:
        await repo.clear_defaults()
    config = ProviderConfig(
        name=name,
        provider=provider,
        model_id=model_id,
        key_ciphertext=encrypt(api_key),
        key_fingerprint=fingerprint(api_key),
        is_default=is_default,
    )
    return await repo.create(config)


async def test_credentials(model_id: str, api_key: Optional[str]) -> dict:
    """Live connection check against the active LLM backend (never raises)."""
    from app.llm import get_llm

    return await get_llm().ping(model_id=model_id, api_key=api_key)


async def test_saved_config(session: AsyncSession, config_id: str) -> Optional[dict]:
    cfg = await ProviderConfigRepository(session).get(config_id)
    if cfg is None:
        return None
    try:
        key = decrypt(cfg.key_ciphertext) if cfg.key_ciphertext else None
    except Exception:  # noqa: BLE001
        key = None
    result = await test_credentials(cfg.model_id, key)
    result["model_id"] = cfg.model_id
    return result


async def resolve_credentials(session: AsyncSession) -> tuple[str, Optional[str]]:
    """Return ``(model_id, api_key)`` from the default provider config, else env."""
    default = await ProviderConfigRepository(session).get_default()
    if default is not None:
        try:
            key = decrypt(default.key_ciphertext) if default.key_ciphertext else None
        except Exception:  # noqa: BLE001
            logger.error("Failed to decrypt provider key; falling back to env")
            key = None
        if key:
            return default.model_id, key
    # No BYOK config: the LiteLLM client selects the provider key (and rotates
    # comma-separated keys) based on the model id, so return key=None here.
    return get_settings().default_model, None
