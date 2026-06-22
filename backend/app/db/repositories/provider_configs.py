"""Provider-config (BYOK) repository."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ProviderConfig


class ProviderConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, config: ProviderConfig) -> ProviderConfig:
        self.session.add(config)
        await self.session.commit()
        await self.session.refresh(config)
        return config

    async def get(self, config_id: str) -> Optional[ProviderConfig]:
        return await self.session.get(ProviderConfig, config_id)

    async def list(self) -> list[ProviderConfig]:
        result = await self.session.execute(
            select(ProviderConfig).order_by(ProviderConfig.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_default(self) -> Optional[ProviderConfig]:
        result = await self.session.execute(
            select(ProviderConfig).where(ProviderConfig.is_default.is_(True))
        )
        return result.scalars().first()

    async def clear_defaults(self) -> None:
        await self.session.execute(
            update(ProviderConfig).values(is_default=False).where(
                ProviderConfig.is_default.is_(True)
            )
        )
        await self.session.commit()

    async def delete(self, config: ProviderConfig) -> None:
        await self.session.delete(config)
        await self.session.commit()
