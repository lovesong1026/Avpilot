"""add reliable task outbox

Revision ID: 9c4c52fd80b1
Revises: 4b7d2a91c6ef
Create Date: 2026-07-24 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9c4c52fd80b1"
down_revision: str | Sequence[str] | None = "4b7d2a91c6ef"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task_outbox",
        sa.Column("task_name", sa.String(length=128), nullable=False),
        sa.Column("queue", sa.String(length=32), nullable=False),
        sa.Column("dedupe_key", sa.String(length=160), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("dispatch_attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("celery_task_id", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key"),
    )
    op.create_index(
        op.f("ix_task_outbox_available_at"), "task_outbox", ["available_at"], unique=False
    )
    op.create_index(
        op.f("ix_task_outbox_celery_task_id"),
        "task_outbox",
        ["celery_task_id"],
        unique=False,
    )
    op.create_index(op.f("ix_task_outbox_queue"), "task_outbox", ["queue"], unique=False)
    op.create_index(op.f("ix_task_outbox_status"), "task_outbox", ["status"], unique=False)
    op.create_index(
        op.f("ix_task_outbox_task_name"), "task_outbox", ["task_name"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_task_outbox_task_name"), table_name="task_outbox")
    op.drop_index(op.f("ix_task_outbox_status"), table_name="task_outbox")
    op.drop_index(op.f("ix_task_outbox_queue"), table_name="task_outbox")
    op.drop_index(op.f("ix_task_outbox_celery_task_id"), table_name="task_outbox")
    op.drop_index(op.f("ix_task_outbox_available_at"), table_name="task_outbox")
    op.drop_table("task_outbox")
