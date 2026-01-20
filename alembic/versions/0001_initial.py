"""initial tables

Revision ID: 0001
Revises: 
Create Date: 2026-01-20
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_clients",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("org_name", sa.String(length=255), nullable=False),
        sa.Column("api_key_hash", sa.String(length=255), nullable=False),
        sa.Column("api_key_sha", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("password_salt", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("TIMEZONE('utc', now())"),
        ),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("api_key_sha"),
    )
    op.create_index("ix_api_clients_email", "api_clients", ["email"], unique=True)

    op.create_table(
        "store_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("api_client_id", sa.Uuid(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("price", sa.Numeric(18, 4), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=True),
        sa.Column("is_exported", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("exported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("TIMEZONE('utc', now())"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("TIMEZONE('utc', now())"),
        ),
        sa.ForeignKeyConstraint(["api_client_id"], ["api_clients.id"]),
        sa.UniqueConstraint("api_client_id", "fingerprint", name="uq_store_item_fingerprint"),
    )
    op.create_index("ix_store_items_api_client", "store_items", ["api_client_id"])
    op.create_index("ix_store_items_fingerprint", "store_items", ["fingerprint"])

    op.create_table(
        "access_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("api_client_id", sa.Uuid(), nullable=False),
        sa.Column("token_sha", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("TIMEZONE('utc', now())"),
        ),
        sa.ForeignKeyConstraint(["api_client_id"], ["api_clients.id"]),
        sa.UniqueConstraint("token_sha"),
    )
    op.create_index("ix_access_tokens_api_client", "access_tokens", ["api_client_id"])
    op.create_index("ix_access_tokens_token_sha", "access_tokens", ["token_sha"], unique=True)

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("api_client_id", sa.Uuid(), nullable=False),
        sa.Column("token_sha", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("TIMEZONE('utc', now())"),
        ),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["api_client_id"], ["api_clients.id"]),
        sa.UniqueConstraint("token_sha"),
    )
    op.create_index("ix_password_reset_tokens_api_client", "password_reset_tokens", ["api_client_id"])
    op.create_index(
        "ix_password_reset_tokens_token_sha",
        "password_reset_tokens",
        ["token_sha"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_store_items_fingerprint", table_name="store_items")
    op.drop_index("ix_store_items_api_client", table_name="store_items")
    op.drop_table("store_items")
    op.drop_index("ix_access_tokens_token_sha", table_name="access_tokens")
    op.drop_index("ix_access_tokens_api_client", table_name="access_tokens")
    op.drop_table("access_tokens")
    op.drop_index("ix_password_reset_tokens_token_sha", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_api_client", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index("ix_api_clients_email", table_name="api_clients")
    op.drop_table("api_clients")
