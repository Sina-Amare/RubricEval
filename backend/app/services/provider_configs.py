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
    settings = get_settings()
    return settings.default_model, settings.openrouter_api_key
