"""add distributor_id to api_clients

Revision ID: 0002
Revises: 0001
Create Date: 2026-01-21
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_clients",
        sa.Column("distributor_id", sa.String(length=255), nullable=False, server_default=""),
    )
    op.create_index("ix_api_clients_distributor_id", "api_clients", ["distributor_id"])


def downgrade() -> None:
    op.drop_index("ix_api_clients_distributor_id", table_name="api_clients")
    op.drop_column("api_clients", "distributor_id")