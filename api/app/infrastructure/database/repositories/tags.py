"""User-scoped tag reuse and content association repository."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.knowledge import Tag, document_tags, image_tags

TAG_COLORS = ["#315F4D", "#52796F", "#5F6F52", "#6B705C", "#4A6C6F", "#7A6C5D"]


def normalize_tag_name(name: str) -> str:
    return "".join(name.strip().casefold().split())[:64]


class TagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_tags(self, user_id: uuid.UUID) -> list[Tag]:
        statement = select(Tag).where(Tag.user_id == user_id).order_by(Tag.name)
        return list(await self.session.scalars(statement))

    async def get_or_create(self, user_id: uuid.UUID, name: str) -> Tag:
        normalized = normalize_tag_name(name)
        if not normalized:
            raise ValueError("标签名称不能为空")
        color = TAG_COLORS[sum(ord(char) for char in normalized) % len(TAG_COLORS)]
        statement = (
            pg_insert(Tag)
            .values(
                id=uuid.uuid4(),
                user_id=user_id,
                name=name.strip()[:64],
                normalized_name=normalized,
                color=color,
                source="ai",
            )
            .on_conflict_do_nothing(index_elements=["user_id", "normalized_name"])
        )
        await self.session.execute(statement)
        tag = await self.session.scalar(
            select(Tag).where(Tag.user_id == user_id, Tag.normalized_name == normalized)
        )
        if tag is None:
            raise RuntimeError("标签创建失败")
        return tag

    async def set_document_tags(
        self, document_id: uuid.UUID, tag_ids: list[uuid.UUID]
    ) -> None:
        await self.session.execute(
            delete(document_tags).where(document_tags.c.document_id == document_id)
        )
        for tag_id in tag_ids:
            await self.session.execute(
                document_tags.insert().values(document_id=document_id, tag_id=tag_id)
            )

    async def set_image_tags(self, image_id: uuid.UUID, tag_ids: list[uuid.UUID]) -> None:
        await self.session.execute(delete(image_tags).where(image_tags.c.image_id == image_id))
        for tag_id in tag_ids:
            await self.session.execute(
                image_tags.insert().values(image_id=image_id, tag_id=tag_id)
            )

    async def document_tags(self, document_id: uuid.UUID) -> list[Tag]:
        statement = (
            select(Tag)
            .join(document_tags, Tag.id == document_tags.c.tag_id)
            .where(document_tags.c.document_id == document_id)
            .order_by(Tag.name)
        )
        return list(await self.session.scalars(statement))

    async def image_tags(self, image_id: uuid.UUID) -> list[Tag]:
        statement = (
            select(Tag)
            .join(image_tags, Tag.id == image_tags.c.tag_id)
            .where(image_tags.c.image_id == image_id)
            .order_by(Tag.name)
        )
        return list(await self.session.scalars(statement))
