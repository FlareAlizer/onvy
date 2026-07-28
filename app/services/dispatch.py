"""Кому уходит реплика и что от неё остаётся в базе.

Связующий слой между разбором команды и доставкой: превращает «скажи кухне» в
список конкретных людей на смене, а результат конвейера — в строки, по которым
потом считается отчёт пилота.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.assistant_query import AssistantQuery, AssistantQueryMenuItem
from app.db.models.comm_group import CommGroup, EmployeeCommGroup
from app.db.models.employee import Employee
from app.db.models.utterance import Utterance
from app.domain.intents import Group
from app.domain.language import Language, normalize
from app.services.assistant_flow import AssistantOutcome
from app.services.comms_flow import Broadcast, Recipient
from app.services.presence import Presence

logger = logging.getLogger(__name__)


async def venue_colleagues(
    db: AsyncSession, venue_id: int, exclude_id: int
) -> list[tuple[int, str]]:
    """Коллеги по точке — для адресной связи по имени в голосовой команде."""
    rows = (
        await db.execute(
            select(Employee.id, Employee.name).where(
                Employee.venue_id == venue_id,
                Employee.id != exclude_id,
                Employee.is_active.is_(True),
                Employee.deleted_at.is_(None),
            )
        )
    ).all()
    return [(row[0], row[1]) for row in rows]


async def resolve_group(
    db: AsyncSession,
    presence: Presence,
    *,
    venue_id: int,
    group: Group,
    exclude_id: int,
) -> tuple[list[Recipient], int | None]:
    """Кому доставлять реплику для группы. Возвращает получателей и id группы.

    Доставляем только тем, кто сейчас на смене: слать в пустоту бессмысленно,
    а копить непрочитанное для рации неправильно — устный разговор не догоняет
    человека через час.
    """
    online = await presence.online(venue_id)
    online.discard(exclude_id)
    if not online:
        return [], None

    group_id: int | None = None
    if group is Group.EVERYONE:
        candidate_ids = online
    else:
        found = (
            await db.execute(
                select(CommGroup.id).where(
                    CommGroup.venue_id == venue_id,
                    CommGroup.name == group.value,
                    CommGroup.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if found is None:
            logger.warning("В точке %s нет группы «%s»", venue_id, group.value)
            return [], None
        group_id = found
        members = (
            (
                await db.execute(
                    select(EmployeeCommGroup.employee_id).where(
                        EmployeeCommGroup.comm_group_id == group_id
                    )
                )
            )
            .scalars()
            .all()
        )
        candidate_ids = online & set(members)

    if not candidate_ids:
        return [], group_id

    rows = (
        await db.execute(
            select(Employee.id, Employee.language).where(
                Employee.id.in_(candidate_ids),
                Employee.venue_id == venue_id,
                Employee.is_active.is_(True),
                Employee.deleted_at.is_(None),
            )
        )
    ).all()
    return [Recipient(employee_id=row[0], language=normalize(row[1])) for row in rows], group_id


async def resolve_person(
    db: AsyncSession, presence: Presence, *, venue_id: int, employee_id: int
) -> list[Recipient]:
    """Адресная доставка. Чужая точка и офлайн-коллега дают пустой список."""
    employee = await db.get(Employee, employee_id)
    if (
        employee is None
        or employee.venue_id != venue_id
        or not employee.is_active
        or employee.deleted_at is not None
    ):
        return []
    if employee.id not in await presence.online(venue_id):
        return []
    return [Recipient(employee_id=employee.id, language=normalize(employee.language))]


async def save_utterance(
    db: AsyncSession,
    *,
    venue_id: int,
    sender_id: int,
    source_language: Language,
    broadcast: Broadcast,
    recipient_employee_id: int | None,
    recipient_group_id: int | None,
    asr_ms: int,
) -> Utterance:
    """Сохранить реплику рации.

    Пишем текст оригинала и перевода, но никогда не аудио и ничего, по чему
    можно опознать человека по голосу — это правовой периметр из спеки.
    Перевод берём у первой доставки: получателей может быть много, а языков
    в смене два-три, и для отчёта важен факт перевода, а не копия на каждого.
    """
    first = broadcast.deliveries[0] if broadcast.deliveries else None
    utterance = Utterance(
        venue_id=venue_id,
        sender_id=sender_id,
        recipient_employee_id=recipient_employee_id,
        recipient_group_id=recipient_group_id,
        source_language=source_language,
        source_text=broadcast.original_text,
        target_language=first.language if first else source_language,
        translated_text=first.text if first and first.translated else None,
        translation_failed=bool(first and first.translation_failed),
        asr_ms=asr_ms,
        translate_ms=first.translate_ms if first else 0,
        tts_ms=first.tts_ms if first else 0,
        total_ms=asr_ms + broadcast.total_ms,
    )
    db.add(utterance)
    await db.flush()
    return utterance


async def save_assistant_query(
    db: AsyncSession,
    *,
    venue_id: int,
    employee_id: int,
    outcome: AssistantOutcome,
) -> AssistantQuery:
    """Сохранить вопрос к ассистенту вместе с метриками стадий.

    menu_item_found=False — это не сбой, а ценные данные: по таким записям видно,
    чего не хватает в меню и какие формулировки официантов мы не понимаем.
    """
    query = AssistantQuery(
        venue_id=venue_id,
        employee_id=employee_id,
        query_text=outcome.query_text,
        answer_text=outcome.answer_text,
        menu_item_found=bool(outcome.grounded_on),
        asr_ms=outcome.metrics.asr_ms,
        llm_ms=outcome.metrics.answer_ms,
        tts_ms=outcome.metrics.tts_ms,
        total_ms=outcome.metrics.total_ms,
    )
    db.add(query)
    await db.flush()

    for external_id in outcome.grounded_on:
        # external_id ручного источника — это строковый id позиции меню.
        if external_id.isdigit():
            db.add(
                AssistantQueryMenuItem(
                    assistant_query_id=query.id, menu_item_id=int(external_id)
                )
            )
    return query
