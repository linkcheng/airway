"""add password_hash to user_mappings

Revision ID: 002
Revises: 001
Create Date: 2026-06-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_mappings", sa.Column("password_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("user_mappings", "password_hash")
