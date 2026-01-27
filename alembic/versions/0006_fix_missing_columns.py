"""Fix missing columns in api_clients table

Revision ID: 0006
Revises: 0005
Create Date: 2026-01-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if columns exist before adding
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("api_clients")]
    
    # Add distributor_id if it doesn't exist
    if "distributor_id" not in columns:
        op.add_column(
            "api_clients",
            sa.Column("distributor_id", sa.String(length=255), nullable=False, server_default=""),
        )
        op.create_index("ix_api_clients_distributor_id", "api_clients", ["distributor_id"])
    
    # Add last_api_key_reset_at if it doesn't exist
    if "last_api_key_reset_at" not in columns:
        op.add_column(
            "api_clients",
            sa.Column("last_api_key_reset_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("api_clients")]
    
    if "last_api_key_reset_at" in columns:
        op.drop_column("api_clients", "last_api_key_reset_at")
    
    if "distributor_id" in columns:
        op.drop_index("ix_api_clients_distributor_id", table_name="api_clients")
        op.drop_column("api_clients", "distributor_id")
