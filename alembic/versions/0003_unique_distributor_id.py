"""enforce unique distributor_id

Revision ID: 0003
Revises: 0002
Create Date: 2026-01-21
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_api_clients_distributor_id",
        "api_clients",
        ["distributor_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_api_clients_distributor_id", "api_clients", type_="unique")