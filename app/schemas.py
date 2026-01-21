import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class ClientRegistrationRequest(BaseModel):
    email: EmailStr = Field(
        ...,
        description="Organization admin email used for login.",
        json_schema_extra={"example": "admin@usepharmacyos.com"},
    )
    org_name: str = Field(
        min_length=2,
        max_length=255,
        description="Organization name displayed in emails.",
        json_schema_extra={"example": "PharmacyOS"},
    )
    distributor_id: str = Field(
        ...,
        description="Distributor identifier from the main system.",
        json_schema_extra={"example": "dist_12345"},
    )
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Password for token exchange (min 8 chars).",
        json_schema_extra={"example": "StrongPass123"},
    )


class ClientRegistrationResponse(BaseModel):
    client_id: uuid.UUID = Field(..., description="Organization identifier.")
    api_key: str = Field(..., description="API key used for /v1/bulk-ingest.")
    distributor_id: str = Field(..., description="Distributor identifier linked to the org.")


class TokenRequest(BaseModel):
    email: EmailStr = Field(
        ...,
        description="Organization admin email.",
        json_schema_extra={"example": "admin@usepharmacyos.com"},
    )
    password: str = Field(
        ...,
        description="Password set at registration.",
        json_schema_extra={"example": "StrongPass123"},
    )


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="Bearer token for automation endpoints.")
    token_type: str = Field("bearer", description="Token type, always 'bearer'.")
    distributor_id: str = Field(..., description="Distributor identifier linked to the org.")


class ApiKeyResetRequest(BaseModel):
    email: EmailStr = Field(
        ...,
        description="Organization admin email.",
        json_schema_extra={"example": "admin@usepharmacyos.com"},
    )
    password: str = Field(
        ...,
        description="Password set at registration.",
        json_schema_extra={"example": "StrongPass123"},
    )


class ApiKeyResetResponse(BaseModel):
    api_key: str = Field(..., description="New API key for /v1/bulk-ingest.")
    distributor_id: str = Field(..., description="Distributor identifier linked to the org.")


class PasswordResetRequest(BaseModel):
    email: EmailStr = Field(
        ...,
        description="Account email to reset.",
        json_schema_extra={"example": "admin@usepharmacyos.com"},
    )


class PasswordResetResponse(BaseModel):
    status: str = Field("ok", description="Request status.")
    reset_token: str | None = Field(
        default=None,
        description="Returned only when RESET_TOKEN_DEBUG=true.",
        json_schema_extra={"example": "reset-token-example"},
    )


class PasswordResetConfirmRequest(BaseModel):
    reset_token: str = Field(
        ...,
        description="Reset token sent via email.",
        json_schema_extra={"example": "abc123-reset-token"},
    )
    new_password: str = Field(
        min_length=8,
        max_length=128,
        description="New password to set.",
        json_schema_extra={"example": "NewStrongPass456"},
    )


class PasswordResetConfirmResponse(BaseModel):
    status: str = Field("ok", description="Reset confirmation status.")


class BulkIngestResponse(BaseModel):
    processed: int = Field(..., description="Number of objects processed.")


class AutomationItem(BaseModel):
    id: uuid.UUID = Field(..., description="Stored item identifier.")
    data: dict[str, Any] = Field(..., description="Original payload stored as JSON.")
    price: float | None = Field(default=None, description="Extracted price value, if present.")
    quantity: float | None = Field(default=None, description="Extracted quantity value, if present.")
    created_at: datetime = Field(..., description="UTC timestamp when first stored.")
    updated_at: datetime = Field(..., description="UTC timestamp when last updated.")

    model_config = {"from_attributes": True}


class AutomationBatchResponse(BaseModel):
    items: list[AutomationItem]
