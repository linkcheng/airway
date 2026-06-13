"""initial user_mappings table

Revision ID: 001
Revises:
Create Date: 2026-06-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    mapping_status = postgresql.ENUM("active", "inactive", name="mappingstatus", create_type=True)
    mapping_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "user_mappings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("clawith_user_id", sa.String(length=255), nullable=False),
        sa.Column("bisheng_user_id", sa.Integer(), nullable=False),
        sa.Column("bisheng_user_name", sa.String(length=255), nullable=False),
        sa.Column("status", mapping_status, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clawith_user_id"),
    )
    op.create_index("ix_user_mappings_clawith_user_id", "user_mappings", ["clawith_user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_mappings_clawith_user_id", table_name="user_mappings")
    op.drop_table("user_mappings")
    mapping_status = postgresql.ENUM("active", "inactive", name="mappingstatus", create_type=True)
    mapping_status.drop(op.get_bind(), checkfirst=True)
