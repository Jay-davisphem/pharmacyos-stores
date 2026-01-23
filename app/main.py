from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
import re

from fastapi import Body, Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import ORJSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    api_key_sha,
    generate_access_token,
    generate_api_key,
    generate_password_salt,
    generate_reset_token,
    get_api_client,
    get_token_client,
    hash_api_key,
    hash_password,
    token_sha,
    verify_password,
)
from app.crud import (
    bulk_upsert_items,
    create_access_token,
    create_api_client,
    create_field_mapping,
    create_password_reset_token,
    fetch_automation_batch,
    get_field_mapping,
    mark_reset_token_used,
    update_api_key,
)
from app.db import create_engine, create_sessionmaker, get_db_session
from app.email_service import EmailService
from app.rate_limit import RateLimiter
from app.models import ApiClient, Base, PasswordResetToken
from app.schemas import (
    ApiKeyResetRequest,
    ApiKeyResetResponse,
    AutomationBatchResponse,
    BulkIngestResponse,
    ClientRegistrationRequest,
    ClientRegistrationResponse,
    PasswordResetConfirmRequest,
    PasswordResetConfirmResponse,
    PasswordResetRequest,
    PasswordResetResponse,
    TokenRequest,
    TokenResponse,
)
from app.settings import Settings, get_settings


def create_app(
    settings: Settings | None = None,
    engine=None,
    sessionmaker=None,
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with app.state.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield
        await app.state.engine.dispose()

    tags_metadata = [
        {"name": "Auth", "description": "Registration, token exchange, and password reset."},
        {"name": "Ingest", "description": "Bulk data ingestion using API keys."},
        {"name": "Automation", "description": "Batch retrieval for automation workflows."},
    ]

    app = FastAPI(
        default_response_class=ORJSONResponse,
        title="Store Bulk API",
        description="Bulk ingest API with per-org automation access and password reset support.",
        version="1.0.0",
        contact={"name": "PharmacyOS", "email": "support@usepharmacyos.com"},
        openapi_tags=tags_metadata,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=settings.allowed_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    engine = engine or create_engine(settings.database_url)
    sessionmaker = sessionmaker or create_sessionmaker(engine)
    app.state.engine = engine
    app.state.sessionmaker = sessionmaker
    app.state.settings = settings
    app.state.rate_limiter = RateLimiter(settings)

    @app.middleware("http")
    async def rate_limit_middleware(request, call_next):
        if request.url.path.startswith("/docs") or request.url.path.startswith("/openapi"):
            return await call_next(request)

        sessionmaker = app.state.sessionmaker
        async with sessionmaker() as session:
            await app.state.rate_limiter.check(request, session)

        return await call_next(request)

    @app.middleware("http")
    async def origin_guard_middleware(request, call_next):
        if request.url.path.startswith("/docs") or request.url.path.startswith("/openapi"):
            return await call_next(request)
        if request.url.path == "/v1/bulk-ingest":
            return await call_next(request)

        origin = request.headers.get("origin")
        if origin:
            if not re.match(settings.allowed_origin_regex, origin):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin not allowed")

        return await call_next(request)

    @app.middleware("http")
    async def host_guard_middleware(request, call_next):
        if request.url.path.startswith("/docs") or request.url.path.startswith("/openapi"):
            return await call_next(request)
        if request.url.path == "/v1/bulk-ingest":
            return await call_next(request)

        host = request.headers.get("host")
        if host and not re.match(r".*\.usepharmacyos\.com$", host):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Host not allowed")

        return await call_next(request)

    @app.post(
        "/v1/clients/register",
        response_model=ClientRegistrationResponse,
        tags=["Auth"],
        summary="Register an organization",
        description=(
            "Creates an organization and returns an API key for bulk ingestion. "
            "Use the same email/password later to request a bearer token."
        ),
        responses={
            200: {
                "description": "Organization registered.",
                "content": {
                    "application/json": {
                        "example": {
                            "client_id": "uuid",
                            "api_key": "sk_example",
                            "distributor_id": "dist_12345",
                        }
                    }
                },
            }
        },
    )
    async def register_client(
        payload: ClientRegistrationRequest = Body(
            ...,
            examples={
                "default": {
                    "summary": "Register an org",
                    "value": {
                        "email": "admin@usepharmacyos.com",
                        "org_name": "PharmacyOS",
                        "distributor_id": "dist_12345",
                        "password": "StrongPass123",
                    },
                }
            },
        ),
        session: AsyncSession = Depends(get_db_session),
    ) -> ClientRegistrationResponse:
        api_key = generate_api_key(settings)
        password_salt = generate_password_salt()
        try:
            client = await create_api_client(
                session,
                email=payload.email,
                org_name=payload.org_name,
                distributor_id=payload.distributor_id,
                api_key_hash=hash_api_key(api_key),
                api_key_sha=api_key_sha(api_key),
                password_hash=hash_password(payload.password, password_salt),
                password_salt=password_salt,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

        return ClientRegistrationResponse(
            client_id=client.id,
            api_key=api_key,
            distributor_id=client.distributor_id,
        )

    @app.post(
        "/v1/auth/token",
        response_model=TokenResponse,
        tags=["Auth"],
        summary="Exchange email/password for a bearer token",
        description="Returns a bearer token to access automation endpoints.",
        responses={
            200: {
                "description": "Token issued.",
                "content": {
                    "application/json": {
                        "example": {
                            "access_token": "token_example",
                            "token_type": "bearer",
                            "distributor_id": "dist_12345",
                        }
                    }
                },
            }
        },
    )
    async def issue_token(
        payload: TokenRequest = Body(
            ...,
            examples={
                "default": {
                    "summary": "Token request",
                    "value": {"email": "admin@usepharmacyos.com", "password": "StrongPass123"},
                }
            },
        ),
        session: AsyncSession = Depends(get_db_session),
    ) -> TokenResponse:
        result = await session.execute(
            select(ApiClient).where(ApiClient.email == payload.email)
        )
        client = result.scalar_one_or_none()
        if not client or not verify_password(payload.password, client.password_salt, client.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        if client.last_api_key_reset_at:
            last_reset = client.last_api_key_reset_at
            if last_reset.tzinfo is None:
                last_reset = last_reset.replace(tzinfo=UTC)
            elapsed = (datetime.now(UTC) - last_reset).total_seconds()
            cooldown = settings.api_key_reset_cooldown_minutes * 60
            if elapsed < cooldown:
                retry_after = int(cooldown - elapsed)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="API key reset cooldown active",
                    headers={"Retry-After": str(retry_after)},
                )

        access_token = generate_access_token()
        await create_access_token(session, client.id, token_sha(access_token))
        return TokenResponse(access_token=access_token, distributor_id=client.distributor_id)

    @app.post(
        "/v1/auth/api-key/reset",
        response_model=ApiKeyResetResponse,
        tags=["Auth"],
        summary="Reset API key",
        description="Regenerates the API key for bulk ingestion using email/password.",
        responses={
            200: {
                "description": "API key rotated.",
                "content": {
                    "application/json": {
                        "example": {"api_key": "sk_new", "distributor_id": "dist_12345"}
                    }
                },
            }
        },
    )
    async def reset_api_key(
        payload: ApiKeyResetRequest = Body(
            ...,
            examples={
                "default": {
                    "summary": "Reset API key",
                    "value": {
                        "email": "admin@usepharmacyos.com",
                        "password": "StrongPass123",
                    },
                }
            },
        ),
        session: AsyncSession = Depends(get_db_session),
    ) -> ApiKeyResetResponse:
        result = await session.execute(
            select(ApiClient).where(ApiClient.email == payload.email)
        )
        client = result.scalar_one_or_none()
        if not client or not verify_password(payload.password, client.password_salt, client.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        if client.last_api_key_reset_at:
            last_reset = client.last_api_key_reset_at
            if last_reset.tzinfo is None:
                last_reset = last_reset.replace(tzinfo=UTC)
            elapsed = (datetime.now(UTC) - last_reset).total_seconds()
            cooldown = settings.api_key_reset_cooldown_minutes * 60
            if elapsed < cooldown:
                retry_after = int(cooldown - elapsed)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="API key reset cooldown active",
                    headers={"Retry-After": str(retry_after)},
                )

        new_api_key = generate_api_key(settings)
        await update_api_key(session, client, hash_api_key(new_api_key), api_key_sha(new_api_key))
        return ApiKeyResetResponse(api_key=new_api_key, distributor_id=client.distributor_id)

    @app.post(
        "/v1/auth/password-reset/request",
        response_model=PasswordResetResponse,
        tags=["Auth"],
        summary="Request a password reset",
        description=(
            "Generates a reset token and sends it via email. "
            "If RESET_TOKEN_DEBUG=true, the token is also returned in the response."
        ),
        responses={
            200: {
                "description": "Reset email queued.",
                "content": {"application/json": {"example": {"status": "ok"}}},
            }
        },
    )
    async def request_password_reset(
        payload: PasswordResetRequest = Body(
            ...,
            examples={
                "default": {
                    "summary": "Request reset",
                    "value": {"email": "admin@usepharmacyos.com"},
                }
            },
        ),
        session: AsyncSession = Depends(get_db_session),
    ) -> PasswordResetResponse:
        result = await session.execute(
            select(ApiClient).where(ApiClient.email == payload.email)
        )
        client = result.scalar_one_or_none()
        if not client:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")

        reset_token = generate_reset_token()
        await create_password_reset_token(session, client.id, token_sha(reset_token))
        email_service = EmailService(settings)
        await email_service.send_reset_email(
            to_email=client.email,
            user_name=client.org_name or client.email,
            token=reset_token,
        )
        if settings.reset_token_debug:
            return PasswordResetResponse(reset_token=reset_token)
        return PasswordResetResponse()

    @app.post(
        "/v1/auth/password-reset/confirm",
        response_model=PasswordResetConfirmResponse,
        tags=["Auth"],
        summary="Confirm a password reset",
        description="Resets the password using the reset token received via email.",
        responses={
            200: {
                "description": "Password updated.",
                "content": {"application/json": {"example": {"status": "ok"}}},
            }
        },
    )
    async def confirm_password_reset(
        payload: PasswordResetConfirmRequest = Body(
            ...,
            examples={
                "default": {
                    "summary": "Confirm reset",
                    "value": {"reset_token": "reset-token", "new_password": "NewStrongPass456"},
                }
            },
        ),
        session: AsyncSession = Depends(get_db_session),
    ) -> PasswordResetConfirmResponse:
        token_hash = token_sha(payload.reset_token)
        result = await session.execute(
            select(PasswordResetToken)
            .where(PasswordResetToken.token_sha == token_hash)
            .where(PasswordResetToken.used_at.is_(None))
        )
        token = result.scalar_one_or_none()
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        password_salt = generate_password_salt()
        password_hash = hash_password(payload.new_password, password_salt)
        await mark_reset_token_used(session, token, password_hash, password_salt)
        return PasswordResetConfirmResponse()

    @app.post(
        "/v1/bulk-ingest",
        response_model=BulkIngestResponse,
        tags=["Ingest"],
        summary="Bulk ingest and upsert items with automatic field detection",
        description=(
            "Ingests a list of JSON objects with automatic AI-powered field detection.\n\n"
            "**Key Features:**\n"
            "- **Automatic Field Detection:** On the first ingest for an organization, the API uses Google Gemini AI "
            "to automatically detect which fields represent `quantity` and `price`, even when named differently "
            "(e.g., `quantity_available`, `unit_price`, `stock`, `cost`).\n"
            "- **Mapping Reuse:** The detected field mapping is stored in the database and reused for all subsequent "
            "ingests for the same organization, eliminating AI overhead after the first request.\n"
            "- **Smart Upsert:** Objects are deduplicated and upserted based on all fields except `price` and `quantity`. "
            "When a matching object is found (all fields except price/quantity match), the existing record is updated with "
            "new price and quantity values.\n"
            "- **Flexible Schema:** Send data with any field names - the API automatically identifies and normalizes them.\n\n"
            "**Authentication:**\n"
            "- Requires header: `X-API-Key: <api_key_from_registration>`\n\n"
            "**Field Detection Behavior:**\n"
            "1. **First Request:** AI analyzes the first object in the batch, detects quantity and price fields, "
            "stores the mapping.\n"
            "2. **Subsequent Requests:** Uses stored mapping (no AI call, faster).\n"
            "3. **Graceful Fallback:** If detection fails or AI is unavailable, processing continues with null field mappings.\n\n"
            "**Similarity Rule:**\n"
            "Two objects are considered the same if all their top-level fields match EXCEPT price and quantity. "
            "When a duplicate is detected, only price and quantity fields are updated; other fields remain unchanged.\n\n"
            "**Rate Limiting:**\n"
            "- 300 requests per 60 seconds per API key and IP address.\n\n"
            "**Batch Size Limit:**\n"
            f"- Maximum {settings.max_batch_size} items per request."
        ),
        responses={
            200: {
                "description": "Batch successfully processed.",
                "content": {
                    "application/json": {
                        "example": {"processed": 2}
                    }
                },
            },
            401: {
                "description": "Unauthorized - Missing or invalid X-API-Key header.",
                "content": {
                    "application/json": {
                        "example": {"detail": "Unauthorized"}
                    }
                },
            },
            413: {
                "description": "Payload Too Large - Batch exceeds max_batch_size limit.",
                "content": {
                    "application/json": {
                        "example": {"detail": "Batch size exceeds limit"}
                    }
                },
            },
        },
    )
    async def bulk_ingest(
        items: list[dict[str, Any]] = Body(
            ...,
            examples={
                "standard_fields": {
                    "summary": "Standard field names (price, quantity)",
                    "description": "First request for an organization with standard field names. "
                    "AI will detect quantity_field='quantity' and price_field='price'.",
                    "value": [
                        {
                            "sku": "SKU-001",
                            "price": 19.99,
                            "quantity": 50,
                            "category": "pain relief",
                            "date": "2026-01-23"
                        },
                        {
                            "sku": "SKU-002",
                            "price": 24.99,
                            "quantity": 30,
                            "category": "vitamins",
                            "date": "2026-01-23"
                        }
                    ],
                },
                "non_standard_fields": {
                    "summary": "Non-standard field names (unit_price, quantity_available)",
                    "description": "First request with alternative field names. "
                    "AI will detect quantity_field='quantity_available' and price_field='unit_price'. "
                    "Subsequent requests with same org can use any field name - the mapping is reused.",
                    "value": [
                        {
                            "sku": "PROD-101",
                            "unit_price": 49.99,
                            "quantity_available": 15,
                            "stock_status": "in stock",
                            "supplier": "Supplier A"
                        },
                        {
                            "sku": "PROD-102",
                            "unit_price": 34.99,
                            "quantity_available": 42,
                            "stock_status": "in stock",
                            "supplier": "Supplier B"
                        }
                    ],
                },
                "update_existing": {
                    "summary": "Update existing items (upsert)",
                    "description": "Sending duplicate SKU with updated price/quantity. "
                    "Matches existing record by all fields except price/quantity, then updates those fields.",
                    "value": [
                        {
                            "sku": "SKU-001",
                            "price": 17.99,
                            "quantity": 60,
                            "category": "pain relief",
                            "date": "2026-01-23"
                        }
                    ],
                },
                "varied_fields": {
                    "summary": "Custom field names with mixed naming",
                    "description": "Real-world example with completely custom field names. "
                    "AI intelligently identifies cost as price and stock as quantity.",
                    "value": [
                        {
                            "product_id": "P001",
                            "cost": 5.50,
                            "stock": 200,
                            "supplier": "Supplier A",
                            "warehouse": "NYC"
                        },
                        {
                            "product_id": "P002",
                            "cost": 7.25,
                            "stock": 150,
                            "supplier": "Supplier B",
                            "warehouse": "LA"
                        }
                    ],
                }
            },
        ),
        client=Depends(get_api_client),
        session: AsyncSession = Depends(get_db_session),
    ) -> BulkIngestResponse:
        if len(items) > settings.max_batch_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Batch size exceeds limit",
            )
        
        # Get or detect field mapping for this organization
        field_mapping = await get_field_mapping(session, client.id)
        
        if not field_mapping:
            # First ingest: detect fields from first object using AI
            quantity_field = None
            price_field = None
            
            if items and settings.gemini_api_key:
                # Use Gemini to detect field names
                from google import genai
                import json
                
                try:
                    client_gemini = genai.Client(api_key=settings.gemini_api_key)
                    sample = items[0]
                    
                    prompt = f"""
Identify which fields represent quantity and price in this retail data.
Data: {json.dumps(sample, indent=2)}

Return JSON with exactly this structure:
{{
  "quantity_field": "<field_name_or_null>",
  "price_field": "<field_name_or_null>"
}}

Only return the JSON, no other text.
"""
                    response = client_gemini.models.generate_content(
                        model=settings.gemini_model,
                        contents=prompt,
                    )
                    result_text = response.text.strip()
                    if result_text.startswith("```json"):
                        result_text = result_text[7:]
                    if result_text.startswith("```"):
                        result_text = result_text[3:]
                    if result_text.endswith("```"):
                        result_text = result_text[:-3]
                    
                    detection = json.loads(result_text)
                    quantity_field = detection.get("quantity_field")
                    price_field = detection.get("price_field")
                except Exception:
                    # Graceful fallback if detection fails
                    pass
            
            # Store the detected (or null) mapping
            await create_field_mapping(session, client.id, quantity_field, price_field)
        else:
            # Reuse stored mapping
            quantity_field = field_mapping.quantity_field
            price_field = field_mapping.price_field
        
        # Ingest using detected fields
        processed = await bulk_upsert_items(
            session, client.id, items, quantity_field=quantity_field, price_field=price_field
        )
        return BulkIngestResponse(processed=processed)

    @app.get(
        "/v1/automation/batch",
        response_model=AutomationBatchResponse,
        tags=["Automation"],
        summary="Fetch a batch for automation",
        description=(
            "Returns unexported items for the authenticated organization. "
            "Requires Authorization: Bearer <token> header from /v1/auth/token."
        ),
        responses={
            200: {
                "description": "Automation batch.",
                "content": {
                    "application/json": {
                        "example": {
                            "items": [
                                {
                                    "id": "uuid",
                                    "data": {"sku": "SKU-1", "price": 10.5},
                                    "price": 10.5,
                                    "quantity": 2,
                                    "created_at": "2026-01-21T10:00:00Z",
                                    "updated_at": "2026-01-21T10:00:00Z",
                                }
                            ]
                        }
                    }
                },
            }
        },
    )
    async def automation_batch(
        limit: int = Query(100, ge=1, le=1000),
        client=Depends(get_token_client),
        session: AsyncSession = Depends(get_db_session),
    ) -> AutomationBatchResponse:
        items = await fetch_automation_batch(session, client.id, limit)
        return AutomationBatchResponse(items=items)

    return app


app = create_app()
