import os

# Тестовое окружение до импорта app.config (Settings читает .env/переменные).
# Пустые YANDEX_* форсируем, чтобы тесты не зависели от реального .env разработчика:
# тесты, которым нужен Yandex, включают его через monkeypatch.
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ["YANDEX_API_KEY"] = ""
os.environ["YANDEX_FOLDER_ID"] = ""

from collections.abc import AsyncGenerator  # noqa: E402

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import Base, get_session  # noqa: E402
from app.main import app  # noqa: E402

# На случай, если .env всё же подхватился раньше — гасим Yandex для базового клиента.
settings.yandex_api_key = ""
settings.yandex_folder_id = ""

API_KEY = os.environ["API_KEY"]


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """HTTP-клиент с изолированной in-memory БД на каждый тест."""
    # StaticPool + один shared-коннект: все сессии видят одну in-memory БД.
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_session() -> AsyncGenerator:
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-API-Key": API_KEY},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()
