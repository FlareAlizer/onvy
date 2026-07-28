"""Rate limiting общего назначения на Redis — скользящее окно (sorted set log).

Точнее фиксированного окна: не даёт всплеска в 2×limit на стыке двух окон.
Используется на входе (защита от подбора PIN распределённым перебором с разных
IP) и должен переиспользоваться на дорогих голосовых роутах (ASR/TTS) — см.
rate_limit_dependency ниже, интеграция в app/api/voice.py и app/api/comms.py
остаётся за лупом, который их пишет.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis

from app.deps import get_redis


@dataclass(frozen=True)
class RateLimitRule:
    limit: int
    window_seconds: int


async def check_rate_limit(redis: Redis, key: str, rule: RateLimitRule) -> None:
    """Учесть текущий запрос и поднять HTTP 429, если лимит окна превышен.

    Реализация — сортированное множество: score = время запроса, member —
    уникальный (время + случайный хвост, чтобы не схлопывались одновременные
    запросы с одинаковым score). Каждый вызов подчищает записи старше окна,
    добавляет текущую и считает размер — атомарно через pipeline.
    """
    now = time.time()
    window_start = now - rule.window_seconds
    member = f"{now}:{uuid.uuid4().hex}"

    pipe = redis.pipeline(transaction=True)
    pipe.zremrangebyscore(key, 0, window_start)
    pipe.zadd(key, {member: now})
    pipe.zcard(key)
    pipe.expire(key, rule.window_seconds)
    results = await pipe.execute()
    count = results[2]

    if count > rule.limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком много запросов, попробуйте позже",
        )


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def rate_limit_dependency(
    rule: RateLimitRule,
    key_prefix: str,
    key_func: Callable[[Request], str] = _client_ip,
):
    """Фабрика зависимости FastAPI: Depends(rate_limit_dependency(RateLimitRule(10, 60), "login")).

    key_func по умолчанию — IP клиента; передайте свою (например, employee_id
    из уже аутентифицированного запроса) для лимита на дорогие голосовые роуты.
    """

    async def dependency(request: Request, redis: Redis = Depends(get_redis)) -> None:
        key = f"ratelimit:{key_prefix}:{key_func(request)}"
        await check_rate_limit(redis, key, rule)

    return dependency
