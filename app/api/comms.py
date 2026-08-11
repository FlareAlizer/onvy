"""Канал рации: постоянное соединение и текстовый запасной путь.

Сокет только принимает — реплики отправляются голосовым роутом. Здесь же
поддерживается отметка «на смене»: телефон, уснувший в кармане, перестаёт
её обновлять и сам выпадает из онлайна.
"""

import base64
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app import adapters
from app.db import get_session
from app.db.models.employee import Employee
from app.deps import CurrentEmployee, get_redis, require_employee
from app.domain.intents import Group
from app.domain.language import normalize
from app.schemas.voice import TextMessageIn, TextMessageResult
from app.services import auth as auth_service
from app.services import dispatch
from app.services.comms_flow import deliver
from app.services.runtime import get_bus, get_presence, registry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["comms"])


@router.post("/comms/text", response_model=TextMessageResult)
async def send_text(
    payload: TextMessageIn,
    current: CurrentEmployee = Depends(require_employee),
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> TextMessageResult:
    """Отправить реплику текстом — когда говорить нельзя или в зале слишком шумно.

    Получатель всё равно слышит её голосом: он в наушнике и в телефон не смотрит.
    """
    presence = get_presence(redis)
    bus = get_bus(redis)
    language = normalize(current.language)

    group_id: int | None = None
    recipient_employee_id: int | None = None

    if payload.recipient_id is not None:
        recipients = await dispatch.resolve_person(
            db, presence, venue_id=current.venue_id, employee_id=payload.recipient_id
        )
        recipient_employee_id = payload.recipient_id
    else:
        try:
            group = Group(payload.group or Group.EVERYONE.value)
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Неизвестная группа: допустимы зал, кухня, бар, все",
            ) from exc
        recipients, group_id = await dispatch.resolve_group(
            db, presence, venue_id=current.venue_id, group=group, exclude_id=current.id
        )

    broadcast = await deliver(
        payload.text,
        source_language=language,
        recipients=recipients,
        translation=adapters.translation(),
        synthesis=adapters.synthesis(),
    )

    utterance = await dispatch.save_utterance(
        db,
        venue_id=current.venue_id,
        sender_id=current.id,
        source_language=language,
        broadcast=broadcast,
        recipient_employee_id=recipient_employee_id,
        recipient_group_id=group_id,
        asr_ms=0,
    )
    await db.commit()

    sender = await db.get(Employee, current.id)
    for delivery in broadcast.deliveries:
        await bus.publish(
            delivery.employee_id,
            {
                "type": "text",
                "utterance_id": utterance.id,
                "from_id": current.id,
                "from_name": sender.name if sender else "",
                "text": delivery.text,
                "language": delivery.language,
                "translated": delivery.translated,
                "translation_failed": delivery.translation_failed,
                "audio_base64": base64.b64encode(delivery.audio).decode("ascii")
                if delivery.audio
                else None,
                "mime_type": delivery.mime_type,
            },
        )

    return TextMessageResult(
        delivered_to=broadcast.delivered_to,
        translation_failed=any(d.translation_failed for d in broadcast.deliveries),
    )


@router.websocket("/ws/comms")
async def comms_socket(websocket: WebSocket) -> None:
    """Канал доставки реплик.

    Авторизация — одноразовым тикетом в query-параметре: заголовки браузерному
    WebSocket недоступны, а токен в URL светился бы в логах прокси. Тикет живёт
    меньше минуты и гасится при первом использовании.
    """
    ticket = websocket.query_params.get("ticket")
    if not ticket:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    redis = websocket.app.state.redis
    data = await auth_service.consume_ws_ticket(redis, ticket)
    if data is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    presence = get_presence(redis)
    bus = get_bus(redis)

    await websocket.accept()
    # Токен этого соединения. Реестр сокетов знает только про свой процесс, а
    # присутствие общее на все реплики: без токена закрытие сокета на одной
    # реплике снимало бы со смены человека, который уже переподключился к
    # другой (см. Presence.leave).
    connection_id = uuid4().hex
    registry.add(data.employee_id, websocket)
    await bus.attach(data.employee_id)
    await presence.join(data.venue_id, data.employee_id, connection_id)
    logger.info("Сотрудник %s на связи", data.employee_id)

    try:
        while True:
            # Клиент шлёт пинг чаще, чем истекает отметка присутствия.
            # Содержимое неважно: сам факт сообщения означает, что он жив.
            await websocket.receive_text()
            await presence.touch(data.venue_id, data.employee_id)
    except WebSocketDisconnect:
        pass
    finally:
        # Уборка раздельная, потому что реестр сокетов локален для процесса, а
        # присутствие — общее на все реплики.
        #
        # Отписка от шины — по локальному реестру: закрылся наш сокет, значит
        # этот процесс сотрудника больше не обслуживает.
        if registry.remove(data.employee_id, websocket):
            await bus.detach(data.employee_id)
        # Со смены снимаем только владельца текущего токена. На плохом вайфае
        # телефон переподключается раньше, чем сервер узнаёт о разрыве старого
        # сокета, — и безусловная уборка гасила свежее соединение: человек
        # оставался «на смене» по пингу, но реплики до него не доходили. Если
        # переподключение попало на другую реплику, локальный реестр этого не
        # видит вовсе — ловит только токен.
        if await presence.leave(data.venue_id, data.employee_id, connection_id):
            logger.info("Сотрудник %s ушёл со связи", data.employee_id)
        else:
            logger.info(
                "Закрылось прошлое соединение сотрудника %s — он уже переподключился",
                data.employee_id,
            )
