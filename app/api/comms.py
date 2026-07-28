"""Связь между сотрудниками (замена рации) — текстом и голосом, с переводом.

- POST /comms/messages — текстовая реплика (one-to-one / broadcast).
- POST /comms/voice    — голосовая реплика: ASR → перевод под язык получателя → TTS.
- WS   /ws/comms/{id}  — канал доставки: сотрудник слушает входящие реплики.

Реплика хранится на языке отправителя; получателю доставляется переведённой.
"""

import base64
import logging

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.deps import require_api_key
from app.models.employee import Employee
from app.models.message import Message
from app.schemas.message import DeliveredMessage, MessageIn, MessageOut
from app.schemas.voice import VoiceCommsResult
from app.services import gamification, speech
from app.services.comms import manager
from app.services.speech import SpeechError
from app.services.translation import default_translator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["comms"])


async def _build_delivered(message: Message, recipient: Employee | None) -> DeliveredMessage:
    """Собрать реплику под язык получателя (перевод, если языки различаются).

    Перевод не должен ронять доставку: если движок перевода недоступен (нет ключа,
    401/сеть), честно доставляем оригинал с translated=False, а не 500 всю рацию.
    """
    target_lang = recipient.language if recipient else message.source_language
    try:
        result = await default_translator.translate(
            message.text, message.source_language, target_lang
        )
    except Exception as exc:  # noqa: BLE001 — перевод не критичен для доставки
        logger.warning(
            "Перевод недоступен (%s→%s): %s. Доставляю оригинал без перевода.",
            message.source_language,
            target_lang,
            exc,
        )
        return DeliveredMessage(
            id=message.id,
            sender_id=message.sender_id,
            recipient_id=message.recipient_id,
            original_text=message.text,
            source_language=message.source_language,
            text=message.text,
            target_language=message.source_language,
            translated=False,
            translation_provider="error",
            created_at=message.created_at,
        )
    return DeliveredMessage(
        id=message.id,
        sender_id=message.sender_id,
        recipient_id=message.recipient_id,
        original_text=message.text,
        source_language=message.source_language,
        text=result.text,
        target_language=result.target_language,
        translated=result.translated,
        translation_provider=result.provider,
        created_at=message.created_at,
    )


async def _recipient_ids(db: AsyncSession, sender: Employee, recipient_id: int | None) -> list[int]:
    """Кому доставлять: конкретному получателю или всем онлайн в отделе (broadcast)."""
    if recipient_id is not None:
        return [recipient_id] if manager.is_online(recipient_id) else []
    # Broadcast — только онлайн-участники того же отдела, кроме отправителя.
    online = set(manager.online_ids()) - {sender.id}
    if not online:
        return []
    rows = (
        (
            await db.execute(
                select(Employee.id).where(
                    Employee.id.in_(online),
                    Employee.department_id == sender.department_id,
                )
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def _store_message(
    db: AsyncSession, sender: Employee, payload_text: str, recipient_id: int | None
) -> Message:
    message = Message(
        sender_id=sender.id,
        recipient_id=recipient_id,
        text=payload_text,
        source_language=sender.language,
    )
    db.add(message)
    await db.flush()
    await db.refresh(message)
    return message


@router.post(
    "/comms/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
async def send_message(payload: MessageIn, db: AsyncSession = Depends(get_session)) -> MessageOut:
    """Текстовая реплика (one-to-one или broadcast при recipient_id=None)."""
    sender = await db.get(Employee, payload.sender_id)
    if sender is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Отправитель не найден")

    message = await _store_message(db, sender, payload.text, payload.recipient_id)
    await gamification.award_points(db, sender.id, gamification.POINTS_MESSAGE)
    await db.commit()

    for employee_id in await _recipient_ids(db, sender, payload.recipient_id):
        recipient = await db.get(Employee, employee_id)
        delivered = await _build_delivered(message, recipient)
        await manager.send_to(employee_id, {"type": "text", **delivered.model_dump(mode="json")})
    return MessageOut.model_validate(message)


@router.post(
    "/comms/voice",
    response_model=VoiceCommsResult,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
async def send_voice(
    audio: UploadFile,
    sender_id: int = Form(...),
    recipient_id: int | None = Form(default=None),
    db: AsyncSession = Depends(get_session),
) -> VoiceCommsResult:
    """Голосовая реплика: распознать → перевести под язык получателя → озвучить."""
    if not settings.yandex_enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Речевой стек Yandex не настроен (YANDEX_API_KEY/YANDEX_FOLDER_ID)",
        )
    sender = await db.get(Employee, sender_id)
    if sender is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Отправитель не найден")

    audio_bytes = await audio.read()
    try:
        text = await speech.recognize(audio_bytes, sender.language)
    except SpeechError as exc:
        logger.error("STT ошибка (comms): %s", exc)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="Ошибка распознавания") from exc

    if not text.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Пустая реплика (тишина)")

    message = await _store_message(db, sender, text, recipient_id)
    await gamification.award_points(db, sender.id, gamification.POINTS_MESSAGE)
    await db.commit()

    delivered_to: list[int] = []
    for employee_id in await _recipient_ids(db, sender, recipient_id):
        recipient = await db.get(Employee, employee_id)
        delivered = await _build_delivered(message, recipient)
        try:
            audio_out = await speech.synthesize(delivered.text, delivered.target_language)
        except SpeechError as exc:
            logger.error("TTS ошибка (comms) для %s: %s", employee_id, exc)
            continue
        payload = {
            "type": "voice",
            **delivered.model_dump(mode="json"),
            "audio_base64": base64.b64encode(audio_out).decode("ascii"),
        }
        if await manager.send_to(employee_id, payload):
            delivered_to.append(employee_id)

    return VoiceCommsResult(
        message_id=message.id,
        recognized_text=text,
        source_language=sender.language,
        delivered_to=delivered_to,
    )


@router.get(
    "/comms/messages",
    response_model=list[MessageOut],
    dependencies=[Depends(require_api_key)],
)
async def list_messages(db: AsyncSession = Depends(get_session)) -> list[Message]:
    """История реплик (для аналитики РОПа)."""
    return list((await db.execute(select(Message))).scalars().all())


@router.websocket("/ws/comms/{employee_id}")
async def comms_ws(websocket: WebSocket, employee_id: int) -> None:
    """Канал доставки: держит сотрудника онлайн и шлёт ему входящие реплики.

    Отправка реплик идёт через POST /comms/voice и /comms/messages. Здесь только
    приём. Аутентификация — по query-параметру ?api_key=... (в браузерном WS
    заголовки недоступны).
    """
    if websocket.query_params.get("api_key") != settings.api_key:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(employee_id, websocket)
    try:
        while True:
            # Держим соединение открытым; входящие пинги от клиента игнорируем.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(employee_id)
