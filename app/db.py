from typing import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def create_engine(database_url: str) -> AsyncEngine:
    # SQLite doesn't support pool_size and max_overflow
    engine_kwargs = {"pool_pre_ping": True}
    if "sqlite" not in database_url.lower():
        engine_kwargs.update({"pool_size": 5, "max_overflow": 10})
    
    return create_async_engine(database_url, **engine_kwargs)


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    sessionmaker = request.app.state.sessionmaker
    async with sessionmaker() as session:
        yield session
