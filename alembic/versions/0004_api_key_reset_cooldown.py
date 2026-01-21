"""add last_api_key_reset_at

Revision ID: 0004
Revises: 0003
Create Date: 2026-01-21
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_clients",
        sa.Column("last_api_key_reset_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("api_clients", "last_api_key_reset_at")