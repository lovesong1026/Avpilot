"""Deep-research tasks, executable steps, and cited evidence."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.models.common import TimestampMixin, UUIDPrimaryKeyMixin


class ResearchTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "research_tasks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(256))
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    stage: Mapped[str] = mapped_column(String(32), default="queued")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    allow_web: Mapped[bool] = mapped_column(Boolean, default=False)
    use_memory: Mapped[bool] = mapped_column(Boolean, default=True)
    knowledge_base_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    plan: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    verifier_result: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    report_markdown: Mapped[str | None] = mapped_column(Text)
    iteration_count: Mapped[int] = mapped_column(Integer, default=0)
    max_iterations: Mapped[int] = mapped_column(Integer, default=2)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)


class ResearchStep(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "research_steps"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_tasks.id", ondelete="CASCADE"),
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer)
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    finding: Mapped[str | None] = mapped_column(Text)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)


class ResearchEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "research_evidence"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_tasks.id", ondelete="CASCADE"),
        index=True,
    )
    step_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_steps.id", ondelete="SET NULL"),
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(24), index=True)
    source_id: Mapped[str] = mapped_column(String(2048))
    chunk_id: Mapped[str | None] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(512))
    quote: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(2048))
    locator: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    score: Mapped[float | None] = mapped_column(Float)
    query: Mapped[str] = mapped_column(Text)
