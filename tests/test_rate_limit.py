"""Тесты скользящего окна rate-limit на Redis (app/services/rate_limit.py).

Fake Redis (fakeredis) вместо реального — см. оговорку в tests/test_auth.py.
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis
from fastapi import Depends, FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis

from app.deps import get_redis
from app.services.rate_limit import RateLimitRule, check_rate_limit, rate_limit_dependency


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator[Redis, None]:
    client = FakeAsyncRedis(decode_responses=True)
    yield client
    await client.aclose()


async def test_allows_requests_within_limit(redis_client: Redis) -> None:
    rule = RateLimitRule(limit=3, window_seconds=60)
    for _ in range(3):
        await check_rate_limit(redis_client, "k1", rule)  # не должно поднять исключение


async def test_blocks_request_over_limit(redis_client: Redis) -> None:
    rule = RateLimitRule(limit=3, window_seconds=60)
    for _ in range(3):
        await check_rate_limit(redis_client, "k1", rule)

    with pytest.raises(HTTPException) as exc_info:
        await check_rate_limit(redis_client, "k1", rule)
    assert exc_info.value.status_code == 429


async def test_different_keys_have_independent_budgets(redis_client: Redis) -> None:
    rule = RateLimitRule(limit=1, window_seconds=60)
    await check_rate_limit(redis_client, "employee:1", rule)
    # Другой ключ (другой сотрудник/IP) не должен быть затронут лимитом первого.
    await check_rate_limit(redis_client, "employee:2", rule)

    with pytest.raises(HTTPException):
        await check_rate_limit(redis_client, "employee:1", rule)


async def test_window_slides_and_frees_budget(
    redis_client: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Старые записи вне окна не учитываются — окно скользит, а не сбрасывается по TTL ключа."""
    import app.services.rate_limit as rl_module

    current_time = [1_000.0]
    monkeypatch.setattr(rl_module.time, "time", lambda: current_time[0])

    rule = RateLimitRule(limit=1, window_seconds=10)
    await check_rate_limit(redis_client, "k", rule)
    with pytest.raises(HTTPException):
        await check_rate_limit(redis_client, "k", rule)

    # Сдвигаем время за пределы окна — старая запись должна быть вычищена.
    current_time[0] += 11
    await check_rate_limit(redis_client, "k", rule)  # снова не должно поднять исключение


async def test_rate_limit_dependency_returns_429_over_http(redis_client: Redis) -> None:
    app = FastAPI()

    async def override_get_redis() -> AsyncGenerator[Redis, None]:
        yield redis_client

    app.dependency_overrides[get_redis] = override_get_redis

    limiter = rate_limit_dependency(RateLimitRule(limit=1, window_seconds=60), key_prefix="test")

    @app.get("/limited", dependencies=[Depends(limiter)])
    async def limited() -> dict:
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.get("/limited")
        assert first.status_code == 200

        second = await client.get("/limited")
        assert second.status_code == 429
        assert second.json()["detail"] == "Слишком много запросов, попробуйте позже"
