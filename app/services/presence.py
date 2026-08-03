"""Кто сейчас на смене и как до него доходит реплика.

Две вещи, которые нельзя было оставить как в демо:

1. Реестр сокетов жил в памяти процесса. При двух воркерах официант и повар
   попадают в разные процессы, и реплика из зала до кухни просто не доходит.
   Теперь доставка идёт через Redis pub/sub: каждый процесс слушает каналы
   только своих подключённых сотрудников и отдаёт им сообщения локально.

2. «Онлайн» тоже был памятью процесса. Теперь это отсортированное множество в
   Redis с отметкой времени: телефон официанта, уснувший в кармане, сам
   выпадает из онлайна по истечении срока, без чистки вручную.
"""

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import WebSocket
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# Сколько живёт отметка «на смене» без подтверждения от клиента. Клиент шлёт
# пинг чаще этого срока; телефон в кармане или потерянный вайфай выпадут сами.
ONLINE_TTL_SECONDS = 45


def _channel(employee_id: int) -> str:
    return f"comms:{employee_id}"


def _online_key(venue_id: int) -> str:
    return f"venue:{venue_id}:online"


class ConnectionRegistry:
    """Живые сокеты этого процесса."""

    def __init__(self) -> None:
        self._sockets: dict[int, WebSocket] = {}

    def add(self, employee_id: int, websocket: WebSocket) -> None:
        self._sockets[employee_id] = websocket

    def remove(self, employee_id: int, websocket: WebSocket | None = None) -> bool:
        """Снять сокет сотрудника. Возвращает True, если сняли именно его.

        `websocket` обязателен везде, где соединение закрывается: телефон в зале
        переподключается на каждой икоте вайфая, и старое соединение закрывается
        уже ПОСЛЕ того, как открылось новое. Безусловный pop в этот момент
        выбрасывал из реестра живой сокет, а вызывающий следом отписывал его от
        шины и снимал со смены. Снаружи это выглядело хуже всего: человек
        числится «на смене» (пинг нового сокета обновляет отметку), а реплики до
        него молча не доходят.
        """
        current = self._sockets.get(employee_id)
        if current is None:
            return False
        if websocket is not None and current is not websocket:
            # Сотрудник уже переподключился — закрывается прошлое соединение.
            return False
        del self._sockets[employee_id]
        return True

    def has(self, employee_id: int) -> bool:
        return employee_id in self._sockets

    async def send(self, employee_id: int, payload: dict[str, Any]) -> bool:
        """Отдать сообщение сокету. Мёртвый сокет снимается, запрос не падает."""
        websocket = self._sockets.get(employee_id)
        if websocket is None:
            return False
        try:
            await websocket.send_json(payload)
        except Exception:  # noqa: BLE001 — сокет мёртв, это не ошибка отправителя
            logger.info("Сокет сотрудника %s мёртв — снимаю", employee_id)
            self.remove(employee_id, websocket)
            return False
        return True


class Presence:
    """Кто на смене, по данным Redis, а не по памяти процесса."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def touch(self, venue_id: int, employee_id: int) -> None:
        """Отметить сотрудника живым. Вызывается при подключении и на каждый пинг."""
        await self._redis.zadd(_online_key(venue_id), {str(employee_id): time.time()})

    async def leave(self, venue_id: int, employee_id: int) -> None:
        await self._redis.zrem(_online_key(venue_id), str(employee_id))

    async def online(self, venue_id: int) -> set[int]:
        """Кто на смене сейчас. Заодно подчищает протухшие отметки."""
        key = _online_key(venue_id)
        cutoff = time.time() - ONLINE_TTL_SECONDS
        await self._redis.zremrangebyscore(key, "-inf", cutoff)
        members = await self._redis.zrange(key, 0, -1)
        return {int(member) for member in members}


class CommsBus:
    """Доставка реплик между процессами.

    Публикуем в канал получателя, слушаем каналы только тех, кто подключён
    именно к нам. Так процесс не разбирает чужой трафик, а подписки живут
    ровно столько, сколько сокет.
    """

    def __init__(self, redis: Redis, registry: ConnectionRegistry) -> None:
        self._redis = redis
        self._registry = registry
        self._pubsub = redis.pubsub(ignore_subscribe_messages=True)
        self._reader: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Запустить фонового читателя. Вызывается на старте приложения."""
        if self._reader is None or self._reader.done():
            self._reader = asyncio.create_task(self._read_forever())

    async def stop(self) -> None:
        if self._reader is not None:
            self._reader.cancel()
            try:
                await self._reader
            except asyncio.CancelledError:
                pass
            self._reader = None
        await self._pubsub.aclose()

    async def attach(self, employee_id: int) -> None:
        """Начать слушать канал сотрудника, подключившегося к этому процессу."""
        await self._pubsub.subscribe(_channel(employee_id))

    async def detach(self, employee_id: int) -> None:
        await self._pubsub.unsubscribe(_channel(employee_id))

    async def publish(self, employee_id: int, payload: dict[str, Any]) -> None:
        """Отправить сообщение сотруднику, где бы он ни был подключён."""
        await self._redis.publish(_channel(employee_id), json.dumps(payload))

    async def _read_forever(self) -> None:
        """Читать шину и раздавать сообщения локальным сокетам.

        Обрыв связи с Redis не должен убивать доставку навсегда: читатель ждёт
        и пробует снова, иначе одна сетевая икота оставит смену без рации.
        """
        while True:
            # Пока к этому процессу никто не подключён, слушать нечего: у pubsub
            # нет ни одного канала, и попытка читать из него — ошибка, а не сбой
            # брокера. Так бывает почти всегда сразу после старта, до первого
            # вошедшего сотрудника.
            if not self._pubsub.subscribed:
                await asyncio.sleep(0.5)
                continue

            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — брокер моргнул, пробуем снова
                logger.warning("Шина связи недоступна (%s), повтор через секунду", exc)
                await asyncio.sleep(1)
                continue

            if message is None:
                continue

            channel = message["channel"]
            if isinstance(channel, bytes):
                channel = channel.decode()
            try:
                employee_id = int(str(channel).split(":", 1)[1])
                payload = json.loads(message["data"])
            except (ValueError, IndexError, json.JSONDecodeError):
                logger.warning("Мусор в шине связи: %r", message)
                continue

            await self._registry.send(employee_id, payload)
