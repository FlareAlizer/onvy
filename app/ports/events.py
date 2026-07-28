"""Порт шины событий: доставка реплик и изменений стоп-листа между процессами.

На пилоте за ним Redis pub/sub. Он нужен не «на вырост», а сразу: uvicorn работает
в несколько воркеров, и WebSocket-соединения сотрудников живут в разных процессах —
без общей шины реплика из зала не дойдёт до повара, подключённого к другому воркеру.
"""

from collections.abc import AsyncIterator
from typing import Any, Protocol


class EventBusPort(Protocol):
    async def publish(self, channel: str, payload: dict[str, Any]) -> None: ...

    def subscribe(self, channel: str) -> AsyncIterator[dict[str, Any]]:
        """Поток событий канала. Реализация переживает обрыв соединения с брокером."""
        ...
