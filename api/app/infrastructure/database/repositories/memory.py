"""PostgreSQL audit repository for memory extraction jobs."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.memory import MemorySource


class MemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, source: MemorySource) -> None:
        self.session.add(source)

    async def get(self, source_id: uuid.UUID) -> MemorySource | None:
        return await self.session.get(MemorySource, source_id)

    async def get_for_user(self, user_id: uuid.UUID, source_id: uuid.UUID) -> MemorySource | None:
        statement = select(MemorySource).where(
            MemorySource.id == source_id,
            MemorySource.user_id == user_id,
        )
        return await self.session.scalar(statement)

    async def list_for_user(self, user_id: uuid.UUID, limit: int = 50) -> list[MemorySource]:
        statement = (
            select(MemorySource)
            .where(MemorySource.user_id == user_id)
            .order_by(MemorySource.created_at.desc())
            .limit(limit)
        )
        return list(await self.session.scalars(statement))
