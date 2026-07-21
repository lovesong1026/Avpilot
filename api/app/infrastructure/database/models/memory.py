"""PostgreSQL audit record for Neo4j memory extraction."""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.models.common import TimestampMixin, UUIDPrimaryKeyMixin


class MemorySource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "memory_sources"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    raw_text: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(16), index=True)
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    graph_source_id: Mapped[str | None] = mapped_column(String(64))
    graph_stats: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
