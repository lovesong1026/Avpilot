"""add conversation knowledge bases

Revision ID: 4b7d2a91c6ef
Revises: bf317a333083
Create Date: 2026-07-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4b7d2a91c6ef"
down_revision: str | Sequence[str] | None = "bf317a333083"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_knowledge_bases",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("knowledge_base_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("conversation_id", "knowledge_base_id"),
    )


def downgrade() -> None:
    op.drop_table("conversation_knowledge_bases")
