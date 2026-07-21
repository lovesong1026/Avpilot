"""User-scoped repositories for conversations, messages, citations, and KB selection."""

import uuid

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.conversation import (
    Citation,
    Conversation,
    Message,
    conversation_knowledge_bases,
)


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_conversations(self, user_id: uuid.UUID) -> list[Conversation]:
        statement = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
        )
        return list(await self.session.scalars(statement))

    async def get(self, user_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation | None:
        statement = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
        return await self.session.scalar(statement)

    def add(self, conversation: Conversation) -> None:
        self.session.add(conversation)

    async def touch(self, conversation_id: uuid.UUID) -> None:
        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=func.now())
        )

    async def knowledge_base_ids(self, conversation_id: uuid.UUID) -> list[uuid.UUID]:
        statement = select(conversation_knowledge_bases.c.knowledge_base_id).where(
            conversation_knowledge_bases.c.conversation_id == conversation_id
        )
        return list(await self.session.scalars(statement))

    async def replace_knowledge_bases(
        self, conversation_id: uuid.UUID, knowledge_base_ids: list[uuid.UUID]
    ) -> None:
        await self.session.execute(
            delete(conversation_knowledge_bases).where(
                conversation_knowledge_bases.c.conversation_id == conversation_id
            )
        )
        if knowledge_base_ids:
            await self.session.execute(
                insert(conversation_knowledge_bases),
                [
                    {"conversation_id": conversation_id, "knowledge_base_id": knowledge_base_id}
                    for knowledge_base_id in dict.fromkeys(knowledge_base_ids)
                ],
            )


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, message: Message) -> None:
        self.session.add(message)

    def add_citation(self, citation: Citation) -> None:
        self.session.add(citation)

    async def list_messages(self, conversation_id: uuid.UUID) -> list[Message]:
        statement = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        return list(await self.session.scalars(statement))

    async def recent(self, conversation_id: uuid.UUID, limit: int = 8) -> list[Message]:
        statement = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return list(reversed(list(await self.session.scalars(statement))))

    async def citations_for_messages(
        self, message_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[Citation]]:
        if not message_ids:
            return {}
        statement = (
            select(Citation)
            .where(Citation.message_id.in_(message_ids))
            .order_by(Citation.created_at.asc())
        )
        grouped: dict[uuid.UUID, list[Citation]] = {}
        for citation in await self.session.scalars(statement):
            grouped.setdefault(citation.message_id, []).append(citation)
        return grouped
