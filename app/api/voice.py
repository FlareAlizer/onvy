"""Голосовой роут: одно нажатие кнопки — один запрос.

Сюда приходит сырой LPCM с телефона официанта. Дальше всё решает распознанная
фраза: вопрос про блюдо уходит ассистенту, «скажи кухне…» — коллегам на смене.
Клиент не выбирает режим заранее, потому что в зале некогда переключать вкладки.
"""

import base64
import logging

from fastapi import APIRouter, Depends, Form, Request, UploadFile
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app import adapters
from app.db import get_session
from app.db.models.employee import Employee
from app.deps import CurrentEmployee, get_redis, require_employee
from app.domain.intents import Group, IntentKind
from app.domain.language import normalize
from app.schemas.voice import AssistantAskIn, StageMetricsOut, VoiceResult
from app.services import dispatch
from app.services.assistant_flow import (
    AssistantOutcome,
    handle_text_query,
    handle_voice_query,
)
from app.services.comms_flow import deliver
from app.services.menu import active_stop_list, load_menu
from app.services.rate_limit import RateLimitRule, rate_limit_dependency
from app.services.runtime import get_bus, get_presence

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voice"])


def _employee_key(request: Request) -> str:
    """Лимит считаем на сотрудника, а не на IP: в чайхане все телефоны сидят
    за одним вайфаем, и лимит по IP наказал бы всю смену за одного."""
    auth = request.headers.get("Authorization", "")
    return auth[-32:] if auth else (request.client.host if request.client else "unknown")


# Каждое нажатие кнопки — это платное распознавание, ответ модели и синтез.
# Заевшая кнопка в кармане или сотрудник, забавляющийся с ассистентом, без
# лимита выжгут квоту облака за смену. 30 нажатий в минуту — заведомо больше,
# чем успевает человек, и заведомо меньше, чем может залипшая кнопка.
_voice_rate_limit = rate_limit_dependency(
    RateLimitRule(limit=30, window_seconds=60), "voice", key_func=_employee_key
)


@router.post(
    "/voice/push-to-talk",
    response_model=VoiceResult,
    dependencies=[Depends(_voice_rate_limit)],
)
async def push_to_talk(
    audio: UploadFile,
    always_on: bool = Form(
        default=False,
        description="Режим постоянного прослушивания: без обращения «Онви» фраза игнорируется",
    ),
    to_group: str | None = Form(
        default=None,
        description="Адресат, выбранный на экране: зал, кухня, бар или все",
    ),
    to_employee_id: int | None = Form(
        default=None, description="Адресат, выбранный на экране: конкретный сотрудник"
    ),
    current: CurrentEmployee = Depends(require_employee),
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> VoiceResult:
    """Обработать запись с кнопки: ответить по меню или передать реплику коллегам."""
    audio_bytes = await audio.read()
    language = normalize(current.language)

    menu = await load_menu(db, current.venue_id)
    stopped = await active_stop_list(db, current.venue_id)
    colleagues = await dispatch.venue_colleagues(db, current.venue_id, current.id)

    outcome = await handle_voice_query(
        audio_bytes,
        language=language,
        menu=menu,
        stopped=stopped,
        colleagues=colleagues,
        recognition=adapters.recognition(),
        answering=adapters.answering(),
        synthesis=adapters.synthesis(),
        require_wake_word=always_on,
    )

    # Адресат, выбранный на экране, применяется когда во фразе обращения не было.
    # Иначе официант, ткнувший пальцем в повара, всё равно был бы обязан назвать
    # его по имени — а он держит поднос и смотрит на гостя, не на телефон.
    if _should_redirect(outcome, to_group, to_employee_id):
        outcome = _redirect_to_chosen(outcome, to_group, to_employee_id, colleagues)

    if outcome.kind in (IntentKind.SEND_GROUP, IntentKind.SEND_PERSON):
        return await _forward_to_colleagues(outcome, current, db, redis, language)

    if outcome.kind is not IntentKind.IGNORED:
        await dispatch.save_assistant_query(
            db, venue_id=current.venue_id, employee_id=current.id, outcome=outcome
        )
        await db.commit()

    return _to_response(outcome)


@router.post(
    "/assistant/ask",
    response_model=VoiceResult,
    dependencies=[Depends(_voice_rate_limit)],
)
async def ask_assistant(
    payload: AssistantAskIn,
    current: CurrentEmployee = Depends(require_employee),
    db: AsyncSession = Depends(get_session),
) -> VoiceResult:
    """Спросить ассистента текстом — тот же ответ по меню, без микрофона.

    Нужен там же, где текстовая реплика коллеге: в шумном зале и при госте,
    когда говорить вслух неудобно.
    """
    language = normalize(current.language)
    menu = await load_menu(db, current.venue_id)
    stopped = await active_stop_list(db, current.venue_id)

    outcome = await handle_text_query(
        payload.text,
        language=language,
        menu=menu,
        stopped=stopped,
        answering=adapters.answering(),
        synthesis=adapters.synthesis(),
        speak=payload.speak,
    )

    await dispatch.save_assistant_query(
        db, venue_id=current.venue_id, employee_id=current.id, outcome=outcome
    )
    await db.commit()

    return _to_response(outcome)


def _should_redirect(
    outcome: AssistantOutcome, to_group: str | None, to_employee_id: int | None
) -> bool:
    """Отдать ли фразу получателю, выбранному на экране, вместо ассистента.

    Правило одно: сказанное вслух сильнее выбранного пальцем. Названный отдел
    («кухня, два лагмана») уже увёл фразу в рацию раньше — сюда доходят только
    вопросы. Из них перенаправляем те, где ассистента вслух не звали: человек
    держит поднос и смотрит на гостя, а не на телефон, и требовать от него имя
    после того, как он ткнул в повара, — лишняя работа.

    Обратное тоже верно: «Онви, что в лагмане» адресовано ассистенту явно, и
    выбранный на экране отдел этот вопрос не перехватывает.
    """
    if outcome.kind is not IntentKind.ASK:
        return False
    if outcome.addressed_assistant:
        return False
    return bool(to_group or to_employee_id)


def _redirect_to_chosen(
    outcome: AssistantOutcome,
    to_group: str | None,
    to_employee_id: int | None,
    colleagues: list,
) -> AssistantOutcome:
    """Отправить фразу тому, кого выбрали на экране, вместо ответа ассистента.

    Сам текст фразы уже распознан — меняем только адресата и вид реплики.
    Ответ ассистента при этом не озвучиваем: его не просили.
    """
    payload = outcome.query_text.strip()
    if not payload:
        return outcome

    if to_employee_id is not None:
        name = next(
            (c.nickname or c.name for c in colleagues if c.id == to_employee_id), None
        )
        if name is None:
            # Выбрали того, кого нет в этой точке — не угадываем, отвечаем как есть.
            logger.warning("Адресат %s не найден в точке", to_employee_id)
            return outcome
        return AssistantOutcome(
            kind=IntentKind.SEND_PERSON,
            query_text=outcome.query_text,
            payload=payload,
            person_id=to_employee_id,
            person_name=name,
            metrics=outcome.metrics,
        )

    try:
        group = Group(to_group or "")
    except ValueError:
        logger.warning("Неизвестная группа с экрана: %r", to_group)
        return outcome
    return AssistantOutcome(
        kind=IntentKind.SEND_GROUP,
        query_text=outcome.query_text,
        payload=payload,
        group=group,
        metrics=outcome.metrics,
    )


async def _forward_to_colleagues(
    outcome: AssistantOutcome,
    current: CurrentEmployee,
    db: AsyncSession,
    redis: Redis,
    language,
) -> VoiceResult:
    """Передать реплику группе или конкретному коллеге, каждому на его языке."""
    presence = get_presence(redis)
    bus = get_bus(redis)

    if outcome.kind is IntentKind.SEND_GROUP and outcome.group is not None:
        recipients, group_id = await dispatch.resolve_group(
            db,
            presence,
            venue_id=current.venue_id,
            group=outcome.group,
            exclude_id=current.id,
        )
        recipient_employee_id = None
    else:
        recipients = await dispatch.resolve_person(
            db, presence, venue_id=current.venue_id, employee_id=outcome.person_id or 0
        )
        group_id = None
        recipient_employee_id = outcome.person_id

    # Ни группы, ни человека — передавать некуда. Раньше такая реплика доходила
    # до базы и валила запрос проверкой single_recipient_kind: официант жал
    # кнопку и получал ошибку вместо ответа. Говорим честно и не пишем битую строку.
    if recipient_employee_id is None and group_id is None:
        logger.warning(
            "Реплика без адресата: kind=%s group=%s person=%s",
            outcome.kind,
            outcome.group,
            outcome.person_id,
        )
        return VoiceResult(
            intent=outcome.kind.value,
            query_text=outcome.query_text,
            answer_text="Не понял, кому передать. Назовите отдел или имя.",
            grounded_on=[],
            degraded=outcome.degraded,
            delivered_to=[],
            metrics=StageMetricsOut(asr_ms=outcome.metrics.asr_ms, total_ms=outcome.metrics.asr_ms),
        )

    broadcast = await deliver(
        outcome.payload,
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
        asr_ms=outcome.metrics.asr_ms,
    )
    await db.commit()

    sender_name = (await db.get(Employee, current.id)).name
    for delivery in broadcast.deliveries:
        await bus.publish(
            delivery.employee_id,
            {
                "type": "voice",
                "utterance_id": utterance.id,
                "from_id": current.id,
                "from_name": sender_name,
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

    # Отправителю подтверждаем словами: он должен знать, что его услышали,
    # не глядя в телефон.
    if broadcast.deliveries:
        confirmation = f"Передал, слышат {len(broadcast.deliveries)}."
    else:
        confirmation = "Никого нет на связи — не передал."

    return VoiceResult(
        intent=outcome.kind.value,
        query_text=outcome.query_text,
        answer_text=confirmation,
        grounded_on=[],
        degraded=outcome.degraded,
        delivered_to=broadcast.delivered_to,
        group=outcome.group.value if outcome.group else None,
        person_name=outcome.person_name,
        metrics=StageMetricsOut(
            asr_ms=outcome.metrics.asr_ms,
            total_ms=outcome.metrics.asr_ms + broadcast.total_ms,
        ),
    )


def _to_response(outcome: AssistantOutcome) -> VoiceResult:
    return VoiceResult(
        intent=outcome.kind.value,
        query_text=outcome.query_text,
        answer_text=outcome.answer_text,
        audio_base64=base64.b64encode(outcome.audio).decode("ascii")
        if outcome.audio
        else None,
        mime_type=outcome.mime_type,
        grounded_on=list(outcome.grounded_on),
        degraded=outcome.degraded,
        metrics=StageMetricsOut(
            asr_ms=outcome.metrics.asr_ms,
            search_ms=outcome.metrics.search_ms,
            answer_ms=outcome.metrics.answer_ms,
            tts_ms=outcome.metrics.tts_ms,
            total_ms=outcome.metrics.total_ms,
        ),
    )
