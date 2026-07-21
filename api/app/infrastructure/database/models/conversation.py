"""Conversation, message, and citation persistence models."""

import uuid

from sqlalchemy import Column, Float, ForeignKey, String, Table, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.models.common import TimestampMixin, UUIDPrimaryKeyMixin

conversation_knowledge_bases = Table(
    "conversation_knowledge_bases",
    Base.metadata,
    Column(
        "conversation_id",
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "knowledge_base_id",
        UUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(256), default="新对话")


class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16), index=True)
    content: Mapped[str] = mapped_column(Text)
    attachments: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB)
    tool_calls: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB)
    usage: Mapped[dict[str, object] | None] = mapped_column(JSONB)


class Citation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "citations"

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(16), index=True)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    chunk_id: Mapped[str | None] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(512))
    locator: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    quote: Mapped[str] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(Float)
