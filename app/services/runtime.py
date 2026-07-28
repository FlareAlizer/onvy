"""Объекты, живущие столько же, сколько процесс: реестр сокетов и шина связи.

Держим их здесь, а не в модуле зависимостей, чтобы жизненный цикл был явным:
шину запускает и останавливает lifespan приложения, а не первый попавшийся запрос.
"""

from redis.asyncio import Redis

from app.services.presence import CommsBus, ConnectionRegistry, Presence

# Сокеты, подключённые именно к этому процессу.
registry = ConnectionRegistry()

_bus: CommsBus | None = None
_presence: Presence | None = None


def get_bus(redis: Redis) -> CommsBus:
    global _bus
    if _bus is None:
        _bus = CommsBus(redis, registry)
    return _bus


def get_presence(redis: Redis) -> Presence:
    global _presence
    if _presence is None:
        _presence = Presence(redis)
    return _presence


async def shutdown() -> None:
    """Остановить фонового читателя шины. Вызывается из lifespan."""
    global _bus
    if _bus is not None:
        await _bus.stop()
        _bus = None
