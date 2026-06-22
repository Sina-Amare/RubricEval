"""BYOK provider-config endpoints (operator-only). Keys are never returned."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_operator
from app.api.schemas.provider import ProviderConfigIn, ProviderConfigOut
from app.db.models import ProviderConfig
from app.db.repositories.provider_configs import ProviderConfigRepository
from app.services.provider_configs import create_provider_config

router = APIRouter(
    prefix="/provider-configs",
    tags=["provider-configs"],
    dependencies=[Depends(require_operator)],
)


def _out(c: ProviderConfig) -> ProviderConfigOut:
    return ProviderConfigOut(
        id=c.id,
        name=c.name,
        provider=c.provider,
        model_id=c.model_id,
        key_fingerprint=c.key_fingerprint,
        is_default=c.is_default,
        created_at=c.created_at,
    )


@router.post("", response_model=ProviderConfigOut, status_code=201)
async def create(
    body: ProviderConfigIn, session: AsyncSession = Depends(get_session)
) -> ProviderConfigOut:
    config = await create_provider_config(
        session,
        name=body.name,
        provider=body.provider,
        model_id=body.model_id,
        api_key=body.api_key,
        is_default=body.is_default,
    )
    return _out(config)


@router.get("", response_model=list[ProviderConfigOut])
async def list_configs(
    session: AsyncSession = Depends(get_session),
) -> list[ProviderConfigOut]:
    return [_out(c) for c in await ProviderConfigRepository(session).list()]


@router.post("/{config_id}/default", response_model=ProviderConfigOut)
async def set_default(
    config_id: str, session: AsyncSession = Depends(get_session)
) -> ProviderConfigOut:
    repo = ProviderConfigRepository(session)
    config = await repo.get(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Provider config not found")
    await repo.clear_defaults()
    config.is_default = True
    await session.commit()
    await session.refresh(config)
    return _out(config)


@router.delete("/{config_id}", status_code=204)
async def delete(
    config_id: str, session: AsyncSession = Depends(get_session)
) -> None:
    repo = ProviderConfigRepository(session)
    config = await repo.get(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Provider config not found")
    await repo.delete(config)
