import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class ClientRegistrationRequest(BaseModel):
    email: EmailStr
    org_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class ClientRegistrationResponse(BaseModel):
    client_id: uuid.UUID
    api_key: str


class TokenRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetResponse(BaseModel):
    status: str = "ok"
    reset_token: str | None = None


class PasswordResetConfirmRequest(BaseModel):
    reset_token: str
    new_password: str = Field(min_length=8, max_length=128)


class PasswordResetConfirmResponse(BaseModel):
    status: str = "ok"


class BulkIngestResponse(BaseModel):
    processed: int


class AutomationItem(BaseModel):
    id: uuid.UUID
    data: dict[str, Any]
    price: float | None
    quantity: float | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AutomationBatchResponse(BaseModel):
    items: list[AutomationItem]
