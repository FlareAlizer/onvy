"""Что происходит на смене и что из этого пойдёт в отчёт по пилоту.

Здесь живут данные, ради которых пилот вообще затевался: сколько раз ассистент
ответил и как быстро, сколько реплик прошло через рацию, где перевод не сработал
и на какие вопросы в меню не нашлось ответа.

Отдельно про честность цифр. Скорость реакции, которую даёт Onvy, — метрика,
которой у заведения раньше не было в принципе, и это сильный аргумент. Но
источник эффекта и источник измерения тут совпадают, поэтому в выгрузке рядом
с цифрами едут сырые записи: их можно перепроверить наблюдением в зале.
"""

import csv
import io
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.menu import require_own_venue
from app.db import get_session
from app.db.models.assistant_query import AssistantQuery
from app.db.models.employee import Employee
from app.db.models.utterance import Utterance
from app.deps import CurrentEmployee, get_redis, require_employee, require_manager
from app.schemas.insights import (
    AssistantQueryOut,
    MetricsSummary,
    PresenceOut,
    UtteranceOut,
)
from app.services.runtime import get_presence

router = APIRouter(tags=["insights"])


@router.get("/venues/{venue_id}/presence", response_model=PresenceOut)
async def presence(
    venue_id: int,
    current: CurrentEmployee = Depends(require_employee),
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> PresenceOut:
    """Кто сейчас на смене.

    Настоящее присутствие, а не догадка по последней реплике: сотрудник
    подтверждает, что жив, пингом по вебсокету, и выпадает сам, если телефон
    уснул в кармане.
    """
    require_own_venue(current, venue_id)
    online = await get_presence(redis).online(venue_id)
    if not online:
        return PresenceOut(online_employee_ids=[], online_names=[])

    names = (
        (
            await db.execute(
                select(Employee.name).where(
                    Employee.id.in_(online), Employee.venue_id == venue_id
                )
            )
        )
        .scalars()
        .all()
    )
    return PresenceOut(online_employee_ids=sorted(online), online_names=list(names))


@router.get("/venues/{venue_id}/utterances", response_model=list[UtteranceOut])
async def recent_utterances(
    venue_id: int,
    limit: int = Query(default=50, le=200),
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> list[UtteranceOut]:
    """Лента реплик рации. Управляющий видит смену целиком, а не только своё."""
    require_own_venue(current, venue_id)
    rows = (
        (
            await db.execute(
                select(Utterance)
                .where(Utterance.venue_id == venue_id)
                .order_by(Utterance.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [
        UtteranceOut(
            id=row.id,
            sender_id=row.sender_id,
            source_language=row.source_language,
            source_text=row.source_text,
            translated_text=row.translated_text,
            target_language=row.target_language,
            translation_failed=row.translation_failed,
            total_ms=row.total_ms,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/venues/{venue_id}/assistant-queries", response_model=list[AssistantQueryOut])
async def recent_queries(
    venue_id: int,
    limit: int = Query(default=50, le=200),
    only_missed: bool = Query(
        default=False, description="Только те, на что ассистент не нашёл ответа в меню"
    ),
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> list[AssistantQueryOut]:
    """Вопросы к ассистенту.

    Ненайденные ответы полезнее найденных: по ним видно, чего не хватает в меню
    и какие формулировки официантов мы не понимаем.
    """
    require_own_venue(current, venue_id)
    query = select(AssistantQuery).where(AssistantQuery.venue_id == venue_id)
    if only_missed:
        query = query.where(AssistantQuery.menu_item_found.is_(False))
    rows = (
        (await db.execute(query.order_by(AssistantQuery.created_at.desc()).limit(limit)))
        .scalars()
        .all()
    )
    return [
        AssistantQueryOut(
            id=row.id,
            employee_id=row.employee_id,
            query_text=row.query_text,
            answer_text=row.answer_text,
            menu_item_found=row.menu_item_found,
            total_ms=row.total_ms,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/venues/{venue_id}/metrics/summary", response_model=MetricsSummary)
async def metrics_summary(
    venue_id: int,
    days: int = Query(default=7, ge=1, le=90),
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> MetricsSummary:
    """Сводка за период — то, что показывают инвестору.

    Латентность считаем по медиане и по 95-му проценнтилю: среднее здесь врёт,
    один зависший запрос перекашивает его целиком, а официанта волнует, как
    часто он ждёт дольше терпимого.
    """
    require_own_venue(current, venue_id)
    since = datetime.now(UTC) - timedelta(days=days)

    queries = (
        (
            await db.execute(
                select(AssistantQuery.total_ms, AssistantQuery.menu_item_found).where(
                    AssistantQuery.venue_id == venue_id,
                    AssistantQuery.created_at >= since,
                )
            )
        )
        .all()
    )
    utterances = (
        await db.execute(
            select(
                func.count(Utterance.id),
                func.count(Utterance.id).filter(Utterance.translation_failed.is_(True)),
                func.count(Utterance.id).filter(Utterance.translated_text.isnot(None)),
            ).where(Utterance.venue_id == venue_id, Utterance.created_at >= since)
        )
    ).one()

    latencies = sorted(row[0] for row in queries if row[0])
    answered = sum(1 for row in queries if row[1])

    return MetricsSummary(
        days=days,
        assistant_queries=len(queries),
        assistant_answered=answered,
        assistant_missed=len(queries) - answered,
        median_ms=_percentile(latencies, 0.5),
        p95_ms=_percentile(latencies, 0.95),
        utterances=utterances[0] or 0,
        translation_failures=utterances[1] or 0,
        translated=utterances[2] or 0,
    )


@router.get("/venues/{venue_id}/metrics/export.csv")
async def export_csv(
    venue_id: int,
    days: int = Query(default=30, ge=1, le=180),
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Сырые записи за период — чтобы цифры отчёта можно было перепроверить."""
    require_own_venue(current, venue_id)
    since = datetime.now(UTC) - timedelta(days=days)

    rows = (
        (
            await db.execute(
                select(AssistantQuery)
                .where(
                    AssistantQuery.venue_id == venue_id,
                    AssistantQuery.created_at >= since,
                )
                .order_by(AssistantQuery.created_at)
            )
        )
        .scalars()
        .all()
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(
        ["время", "сотрудник", "вопрос", "ответ", "нашлось в меню", "мс всего", "мс распознавание"]
    )
    for row in rows:
        writer.writerow(
            [
                row.created_at.isoformat(),
                row.employee_id,
                row.query_text,
                row.answer_text,
                "да" if row.menu_item_found else "нет",
                row.total_ms or "",
                row.asr_ms or "",
            ]
        )

    # utf-8-sig: Excel на русской Windows иначе покажет вместо текста кашу.
    payload = buffer.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        io.BytesIO(payload),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="onvy-{venue_id}-{days}d.csv"'
        },
    )


def _percentile(values: list[int], fraction: float) -> int | None:
    """Процентиль по отсортированному списку. Пусто — значит нечего показывать."""
    if not values:
        return None
    index = min(int(len(values) * fraction), len(values) - 1)
    return values[index]
