import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Uuid


class Base(DeclarativeBase):
    pass


class ApiClient(Base):
    __tablename__ = "api_clients"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    org_name: Mapped[str] = mapped_column(String(255))
    distributor_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    api_key_hash: Mapped[str] = mapped_column(String(255))
    api_key_sha: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    password_salt: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    last_api_key_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["StoreItem"]] = relationship(back_populates="api_client")
    tokens: Mapped[list["AccessToken"]] = relationship(back_populates="api_client")
    reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(back_populates="api_client")


class StoreItem(Base):
    __tablename__ = "store_items"
    __table_args__ = (
        UniqueConstraint("api_client_id", "fingerprint", name="uq_store_item_fingerprint"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    api_client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("api_clients.id"), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    data: Mapped[dict] = mapped_column(JSON)
    price: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    quantity: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    is_exported: Mapped[bool] = mapped_column(Boolean, default=False)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    api_client: Mapped[ApiClient] = relationship(back_populates="items")


class AccessToken(Base):
    __tablename__ = "access_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    api_client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("api_clients.id"), index=True)
    token_sha: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    api_client: Mapped[ApiClient] = relationship(back_populates="tokens")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    api_client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("api_clients.id"), index=True)
    token_sha: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    api_client: Mapped[ApiClient] = relationship(back_populates="reset_tokens")


class FieldMapping(Base):
    __tablename__ = "field_mappings"
    __table_args__ = (
        UniqueConstraint("api_client_id", name="uq_field_mapping_per_client"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    api_client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("api_clients.id"), index=True)
    quantity_field: Mapped[str | None] = mapped_column(String(255), nullable=True)
    price_field: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    api_client: Mapped[ApiClient] = relationship()
