"""Realtime-связь между сотрудниками (замена рации).

ConnectionManager держит активные WebSocket-подключения по employee_id и
рассылает реплики: one-to-one, broadcast и с переводом под язык получателя.
Для MVP это in-memory (один процесс); на рост — вынести в Redis pub/sub.
"""

import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Реестр активных подключений сотрудников."""

    def __init__(self) -> None:
        self._connections: dict[int, WebSocket] = {}

    async def connect(self, employee_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[employee_id] = websocket
        logger.info("Сотрудник %s подключился к связи", employee_id)

    def disconnect(self, employee_id: int) -> None:
        self._connections.pop(employee_id, None)
        logger.info("Сотрудник %s отключился от связи", employee_id)

    def is_online(self, employee_id: int) -> bool:
        return employee_id in self._connections

    def online_ids(self) -> list[int]:
        return list(self._connections)

    async def send_to(self, employee_id: int, payload: dict) -> bool:
        """Отправить payload одному сотруднику. True, если доставлено.

        Мёртвый сокет (телефон уснул/сеть отвалилась без close-кадра) не должен
        ронять запрос: считаем такого получателя офлайн и убираем из реестра.
        """
        ws = self._connections.get(employee_id)
        if ws is None:
            return False
        try:
            await ws.send_json(payload)
        except Exception:  # noqa: BLE001 — сокет мёртв, доставка не удалась
            logger.info("Сокет сотрудника %s мёртв — снимаю с онлайна", employee_id)
            self.disconnect(employee_id)
            return False
        return True

    async def broadcast(self, payload: dict, exclude: int | None = None) -> list[int]:
        """Разослать всем онлайн, кроме exclude. Возвращает реально доставленных."""
        delivered: list[int] = []
        for employee_id in list(self._connections):
            if employee_id == exclude:
                continue
            if await self.send_to(employee_id, payload):
                delivered.append(employee_id)
        return delivered


# Единый менеджер на процесс.
manager = ConnectionManager()
