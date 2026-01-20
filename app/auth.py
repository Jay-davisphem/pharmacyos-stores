import hashlib
import hmac
import secrets

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.models import AccessToken, ApiClient
from app.settings import Settings


def generate_api_key(settings: Settings) -> str:
    token = secrets.token_urlsafe(settings.api_key_length)
    return f"{settings.api_key_prefix}{token}"


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def api_key_sha(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def verify_api_key(api_key: str, hashed: str) -> bool:
    computed = hash_api_key(api_key)
    return hmac.compare_digest(computed, hashed)


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        200_000,
    ).hex()


def generate_password_salt() -> str:
    return secrets.token_urlsafe(16)


def verify_password(password: str, salt: str, password_hash: str) -> bool:
    computed = hash_password(password, salt)
    return hmac.compare_digest(computed, password_hash)


def generate_access_token() -> str:
    return secrets.token_urlsafe(40)


def token_sha(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


async def get_api_client(
    api_key: str = Header(alias="X-API-Key"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiClient:
    sha = api_key_sha(api_key)
    result = await session.execute(select(ApiClient).where(ApiClient.api_key_sha == sha))
    client = result.scalar_one_or_none()
    if not client or not verify_api_key(api_key, client.api_key_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return client


async def get_token_client(
    authorization: str = Header(alias="Authorization"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiClient:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    token = authorization.split(" ", 1)[1].strip()
    token_hash = token_sha(token)
    result = await session.execute(
        select(ApiClient)
        .join(AccessToken)
        .where(AccessToken.token_sha == token_hash)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return client
