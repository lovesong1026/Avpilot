"""Establish the initial empty schema baseline.

Revision ID: 0001
Revises:
Create Date: 2026-07-20
"""

from collections.abc import Sequence

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Reserve the initial schema revision before domain tables are introduced."""


def downgrade() -> None:
    """The baseline has no schema objects to remove."""
