"""Daily review persistence model."""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.models.common import TimestampMixin, UUIDPrimaryKeyMixin


class DailyReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "daily_reviews"
    __table_args__ = (UniqueConstraint("user_id", "review_date", name="uq_daily_review_user_date"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    review_date: Mapped[date] = mapped_column(Date, index=True)
    content: Mapped[str] = mapped_column(Text)
    stats: Mapped[dict[str, object] | None] = mapped_column(JSONB)
