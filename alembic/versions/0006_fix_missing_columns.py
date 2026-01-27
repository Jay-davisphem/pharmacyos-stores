"""Fix missing columns in api_clients table

Revision ID: 0006
Revises: 0005
Create Date: 2026-01-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add distributor_id if it doesn't exist
    try:
        op.add_column(
            "api_clients",
            sa.Column("distributor_id", sa.String(length=255), nullable=False, server_default=""),
        )
        op.create_index("ix_api_clients_distributor_id", "api_clients", ["distributor_id"])
    except Exception:
        # Column already exists, skip
        pass

    # Add last_api_key_reset_at if it doesn't exist
    try:
        op.add_column(
            "api_clients",
            sa.Column("last_api_key_reset_at", sa.DateTime(timezone=True), nullable=True),
        )
    except Exception:
        # Column already exists, skip
        pass


def downgrade() -> None:
    op.drop_column("api_clients", "last_api_key_reset_at")
    op.drop_index("ix_api_clients_distributor_id", table_name="api_clients")
    op.drop_column("api_clients", "distributor_id")
