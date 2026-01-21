import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import delete

from app.db import create_engine, create_sessionmaker
from app.main import create_app
from app.models import ApiClient, Base, StoreItem
from app.settings import Settings


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings(tmp_path):
    db_path = tmp_path / "test.db"
    return Settings(
        database_url=f"sqlite+aiosqlite:///{db_path}",
        max_batch_size=1000,
        email_provider="console",
        reset_token_debug=True,
        api_key_reset_cooldown_minutes=60,
    )


@pytest_asyncio.fixture
async def engine(test_settings):
    engine = create_engine(test_settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    sessionmaker = create_sessionmaker(engine)
    async with sessionmaker() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_settings, engine):
    sessionmaker = create_sessionmaker(engine)
    app = create_app(test_settings, engine=engine, sessionmaker=sessionmaker)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://app.usepharmacyos.com") as client:
        yield client
