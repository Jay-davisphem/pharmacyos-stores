from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import api_key_sha, token_sha
from app.models import AccessToken, ApiClient
from app.settings import Settings


@dataclass
class RateLimitEntry:
    window_start: float
    count: int


class RateLimiter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = asyncio.Lock()
        self._entries: dict[str, RateLimitEntry] = {}
        self._client_cache: dict[str, tuple[str, float]] = {}

    async def resolve_client_id(self, session: AsyncSession, request: Request) -> Optional[str]:
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return await self._lookup_api_key(session, api_key)

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            return await self._lookup_token(session, token)

        return None

    async def _lookup_api_key(self, session: AsyncSession, api_key: str) -> Optional[str]:
        cache_key = f"api:{api_key}" 
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        key_sha = api_key_sha(api_key)
        result = await session.execute(select(ApiClient.id).where(ApiClient.api_key_sha == key_sha))
        client_id = result.scalar_one_or_none()
        if client_id:
            self._set_cached(cache_key, str(client_id))
        return str(client_id) if client_id else None

    async def _lookup_token(self, session: AsyncSession, token: str) -> Optional[str]:
        cache_key = f"token:{token}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        token_hash = token_sha(token)
        result = await session.execute(
            select(ApiClient.id)
            .join(AccessToken, AccessToken.api_client_id == ApiClient.id)
            .where(AccessToken.token_sha == token_hash)
        )
        client_id = result.scalar_one_or_none()
        if client_id:
            self._set_cached(cache_key, str(client_id))
        return str(client_id) if client_id else None

    def _get_cached(self, key: str) -> Optional[str]:
        cached = self._client_cache.get(key)
        if not cached:
            return None
        value, expires_at = cached
        if time.time() > expires_at:
            self._client_cache.pop(key, None)
            return None
        return value

    def _set_cached(self, key: str, value: str) -> None:
        self._client_cache[key] = (value, time.time() + 60)

    def _get_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
        return request.client.host if request.client else "unknown"

    async def check(self, request: Request, session: AsyncSession) -> None:
        ip = self._get_ip(request)
        client_id = await self.resolve_client_id(session, request)
        key = f"{client_id or 'anon'}:{ip}"

        now = time.time()
        window = self.settings.rate_limit_window_seconds
        limit = self.settings.rate_limit_requests

        async with self._lock:
            entry = self._entries.get(key)
            if not entry or now - entry.window_start >= window:
                self._entries[key] = RateLimitEntry(window_start=now, count=1)
                return

            if entry.count >= limit:
                retry_after = max(1, int(window - (now - entry.window_start)))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": str(retry_after)},
                )

            entry.count += 1