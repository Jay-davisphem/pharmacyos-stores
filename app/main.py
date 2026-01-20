from contextlib import asynccontextmanager
from typing import Any

from fastapi import Body, Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import ORJSONResponse
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
    create_password_reset_token,
    fetch_automation_batch,
    mark_reset_token_used,
)
from app.db import create_engine, create_sessionmaker, get_db_session
from app.email_service import EmailService
from app.rate_limit import RateLimiter
from app.models import ApiClient, Base, PasswordResetToken
from app.schemas import (
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

    @app.post("/v1/clients/register", response_model=ClientRegistrationResponse, tags=["Auth"])
    async def register_client(
        payload: ClientRegistrationRequest,
        session: AsyncSession = Depends(get_db_session),
    ) -> ClientRegistrationResponse:
        api_key = generate_api_key(settings)
        password_salt = generate_password_salt()
        try:
            client = await create_api_client(
                session,
                email=payload.email,
                org_name=payload.org_name,
                api_key_hash=hash_api_key(api_key),
                api_key_sha=api_key_sha(api_key),
                password_hash=hash_password(payload.password, password_salt),
                password_salt=password_salt,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

        return ClientRegistrationResponse(client_id=client.id, api_key=api_key)

    @app.post("/v1/auth/token", response_model=TokenResponse, tags=["Auth"])
    async def issue_token(
        payload: TokenRequest,
        session: AsyncSession = Depends(get_db_session),
    ) -> TokenResponse:
        result = await session.execute(
            select(ApiClient).where(ApiClient.email == payload.email)
        )
        client = result.scalar_one_or_none()
        if not client or not verify_password(payload.password, client.password_salt, client.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        access_token = generate_access_token()
        await create_access_token(session, client.id, token_sha(access_token))
        return TokenResponse(access_token=access_token)

    @app.post("/v1/auth/password-reset/request", response_model=PasswordResetResponse, tags=["Auth"])
    async def request_password_reset(
        payload: PasswordResetRequest,
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

    @app.post("/v1/auth/password-reset/confirm", response_model=PasswordResetConfirmResponse, tags=["Auth"])
    async def confirm_password_reset(
        payload: PasswordResetConfirmRequest,
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

    @app.post("/v1/bulk-ingest", response_model=BulkIngestResponse, tags=["Ingest"])
    async def bulk_ingest(
        items: list[dict[str, Any]] = Body(...),
        client=Depends(get_api_client),
        session: AsyncSession = Depends(get_db_session),
    ) -> BulkIngestResponse:
        if len(items) > settings.max_batch_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Batch size exceeds limit",
            )
        processed = await bulk_upsert_items(session, client.id, items)
        return BulkIngestResponse(processed=processed)

    @app.get("/v1/automation/batch", response_model=AutomationBatchResponse, tags=["Automation"])
    async def automation_batch(
        limit: int = Query(100, ge=1, le=1000),
        client=Depends(get_token_client),
        session: AsyncSession = Depends(get_db_session),
    ) -> AutomationBatchResponse:
        items = await fetch_automation_batch(session, client.id, limit)
        return AutomationBatchResponse(items=items)

    return app


app = create_app()
