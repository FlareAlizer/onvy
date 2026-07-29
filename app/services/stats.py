"""Расчёт статистики сотрудника, прогресса KPI, агрегации FAQ/смен и оценки
тестов поверх сырых данных (utterances, assistant_queries).

Слой намеренно разделён на чистые функции (без БД, без FastAPI — легко
проверяются юнит-тестами в tests/test_stats.py без Postgres) и тонкие
async-обёртки с сессией, которые только достают сырые строки и передают их
в чистую логику. Локальный запуск (нет Docker/Postgres на этой машине,
см. tests/conftest.py) не может прогнать вторые — поэтому вся расчётная
логика вынесена в первые.

Честность цифр (задание лупа): revenue/avg_check не считаются нигде в этом
модуле — источник (POS) отсутствует. Там, где фронт (frontend/src/types.ts)
ожидает такие поля, их отдают как None с пометкой источника на уровне схемы
(app/schemas/staff.py), а не выдумывают.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.assistant_query import AssistantQuery
from app.db.models.comm_group import CommGroup
from app.db.models.utterance import Utterance

# Группы, обращение в которые считается "обращением за помощью" сотрудника
# (EmployeeStats.helpRequests фронта). Спека групп (specs/pilot-chaihana.md §4):
# зал/кухня/бар/все — из них помощью коллег по факту являются кухня и бар.
_HELP_GROUP_NAMES = frozenset({"кухня", "бар"})


# --- Периоды KPI ---------------------------------------------------------------


def period_bounds(period: str, on: date) -> tuple[date, date]:
    """Границы периода (включительно), которому принадлежит дата `on`.

    "week" — понедельник..воскресенье (ISO), "month" — 1-е число..последний
    день месяца, "day" — сама дата. Часовой пояс точки не учитывается здесь —
    вызывающий код обязан передать уже локальную для точки дату.
    """
    if period == "day":
        return on, on
    if period == "week":
        start = on - timedelta(days=on.weekday())
        return start, start + timedelta(days=6)
    if period == "month":
        start = on.replace(day=1)
        if start.month == 12:
            next_month_start = start.replace(year=start.year + 1, month=1)
        else:
            next_month_start = start.replace(month=start.month + 1)
        return start, next_month_start - timedelta(days=1)
    raise ValueError(f"Неизвестный период: {period!r}")


def kpi_progress_percent(current: Decimal | float, target: Decimal | float) -> float | None:
    """Процент выполнения цели. target=0 и current=0 — цель выполнена (100%);
    target=0 и current>0 — прогресс не определён (деление на ноль не значит
    "бесконечность", честнее вернуть None)."""
    target_f = float(target)
    current_f = float(current)
    if target_f == 0:
        return 100.0 if current_f == 0 else None
    return round(current_f / target_f * 100, 1)


# --- Метрики сотрудника ---------------------------------------------------------


def autonomy_percent(total_queries: int, found_queries: int) -> float | None:
    """Доля вопросов к ассистенту, закрытых им самим (menu_item_found=True),
    без обращения к коллегам. None — вопросов не было, а не 0%: 0 значило бы
    "ни один вопрос не решён сам", что вводит в заблуждение при их отсутствии."""
    if total_queries == 0:
        return None
    return round(found_queries / total_queries * 100, 1)


def avg_response_seconds(total_ms_values: list[int | None]) -> float | None:
    """Среднее время ответа в секундах по стадиям total_ms. Пропускает записи
    без метрики (деградация могла не измерить стадию — см. spec §6)."""
    values = [v for v in total_ms_values if v is not None]
    if not values:
        return None
    return round(sum(values) / len(values) / 1000, 2)


@dataclass(frozen=True)
class EmployeeStatsResult:
    """EmployeeStats фронта (frontend/src/types.ts), но честно про источники:
    revenue/avg_check/conversion/script_compliance здесь нет — без POS-
    интеграции их не из чего посчитать (см. докстринг модуля)."""

    employee_id: int
    period_days: int
    dialogs: int
    response_sec: float | None
    autonomy_percent: float | None
    help_requests: int


def compute_employee_stats(
    *,
    employee_id: int,
    period_days: int,
    query_total_ms: list[int | None],
    query_found: list[bool],
    utterance_total_ms: list[int | None],
    help_request_count: int,
) -> EmployeeStatsResult:
    """Чистая часть employee_stats() — вход уже выбран из БД вызывающим кодом."""
    if len(query_total_ms) != len(query_found):
        raise ValueError("query_total_ms и query_found должны быть одной длины")
    dialogs = len(query_total_ms) + len(utterance_total_ms)
    return EmployeeStatsResult(
        employee_id=employee_id,
        period_days=period_days,
        dialogs=dialogs,
        response_sec=avg_response_seconds(query_total_ms + utterance_total_ms),
        autonomy_percent=autonomy_percent(len(query_found), sum(query_found)),
        help_requests=help_request_count,
    )


async def employee_stats(
    session: AsyncSession,
    venue_id: int,
    employee_id: int,
    *,
    since: datetime,
    period_days: int,
    until: datetime | None = None,
) -> EmployeeStatsResult:
    """Статистика сотрудника за окно [since, until) — until=None значит "по
    сейчас". DB-обёртка над compute_employee_stats."""
    query_stmt = select(AssistantQuery.total_ms, AssistantQuery.menu_item_found).where(
        AssistantQuery.venue_id == venue_id,
        AssistantQuery.employee_id == employee_id,
        AssistantQuery.created_at >= since,
    )
    utterance_stmt = select(Utterance.total_ms, Utterance.recipient_group_id).where(
        Utterance.venue_id == venue_id,
        Utterance.sender_id == employee_id,
        Utterance.created_at >= since,
    )
    if until is not None:
        query_stmt = query_stmt.where(AssistantQuery.created_at < until)
        utterance_stmt = utterance_stmt.where(Utterance.created_at < until)

    queries = (await session.execute(query_stmt)).all()
    utterances = (await session.execute(utterance_stmt)).all()
    help_group_ids = await _help_group_ids(session, venue_id)
    help_request_count = sum(
        1 for _, group_id in utterances if group_id is not None and group_id in help_group_ids
    )

    return compute_employee_stats(
        employee_id=employee_id,
        period_days=period_days,
        query_total_ms=[row[0] for row in queries],
        query_found=[bool(row[1]) for row in queries],
        utterance_total_ms=[row[0] for row in utterances],
        help_request_count=help_request_count,
    )


async def _help_group_ids(session: AsyncSession, venue_id: int) -> frozenset[int]:
    """id живых групп точки, обращение в которые считается обращением за
    помощью (см. _HELP_GROUP_NAMES). Сверка имени — в Python (casefold), не
    в SQL: групп на точку единицы, а casefold честнее lower() для не-ASCII
    названий на будущее."""
    rows = (
        await session.execute(
            select(CommGroup.id, CommGroup.name).where(
                CommGroup.venue_id == venue_id,
                CommGroup.deleted_at.is_(None),
            )
        )
    ).all()
    return frozenset(
        group_id for group_id, name in rows if name.strip().casefold() in _HELP_GROUP_NAMES
    )


# --- Смены сотрудника (замена "диалога" фронта, п.3 задания) --------------------


@dataclass(frozen=True)
class ShiftEvent:
    """Одно событие смены — реплика рации или вопрос к ассистенту."""

    kind: str  # "utterance" | "assistant_query"
    at: datetime
    text: str
    detail: str | None  # перевод (utterance) или ответ ассистента (assistant_query)
    total_ms: int | None
    menu_item_found: bool | None = None  # только для assistant_query
    is_help_request: bool = False  # utterance адресован в группу "кухня"/"бар"


@dataclass(frozen=True)
class ShiftSummary:
    """Смена сотрудника за календарный день — наша честная замена интерфейсу
    `Dialog` фронта (frontend/src/types.ts): у нас нет понятия завершённого
    обслуживания одного гостя, есть поток реплик рации и вопросов к
    ассистенту за смену. `wave` и AI-`moments` фронта здесь не считаются —
    источник для них не в этом лупе (см. отчёт лупа), поля сознательно не
    заводим, а не заполняем нулями/пустышками под видом реальных данных.

    Группировка по календарной дате created_at (UTC) — приближение к границе
    смены, без учёта Venue.timezone: смена, пересекающая полночь по местному
    времени точки, может разъехаться на два дня. Точная граница смены —
    отдельная задача не в этом лупе.
    """

    shift_date: date
    employee_id: int
    started_at: datetime | None
    ended_at: datetime | None
    utterances_count: int
    assistant_queries_count: int
    help_requests: int
    response_sec: float | None
    events: list[ShiftEvent] = field(default_factory=list)


def group_events_into_shifts(events: list[ShiftEvent], *, employee_id: int) -> list[ShiftSummary]:
    """Сгруппировать события сотрудника по календарному дню — от новых к старым."""
    by_date: dict[date, list[ShiftEvent]] = defaultdict(list)
    for event in events:
        by_date[event.at.date()].append(event)

    summaries: list[ShiftSummary] = []
    for shift_date in sorted(by_date, reverse=True):
        day_events = sorted(by_date[shift_date], key=lambda e: e.at)
        utterances = [e for e in day_events if e.kind == "utterance"]
        queries = [e for e in day_events if e.kind == "assistant_query"]
        summaries.append(
            ShiftSummary(
                shift_date=shift_date,
                employee_id=employee_id,
                started_at=day_events[0].at if day_events else None,
                ended_at=day_events[-1].at if day_events else None,
                utterances_count=len(utterances),
                assistant_queries_count=len(queries),
                help_requests=sum(1 for e in utterances if e.is_help_request),
                response_sec=avg_response_seconds([e.total_ms for e in day_events]),
                events=day_events,
            )
        )
    return summaries


async def load_shift_events(
    session: AsyncSession,
    venue_id: int,
    employee_id: int,
    *,
    since: datetime,
    until: datetime | None = None,
) -> list[ShiftEvent]:
    """Сырые события смены сотрудника за окно — вход для group_events_into_shifts."""
    help_group_ids = await _help_group_ids(session, venue_id)

    utterance_stmt = select(Utterance).where(
        Utterance.venue_id == venue_id,
        Utterance.sender_id == employee_id,
        Utterance.created_at >= since,
    )
    if until is not None:
        utterance_stmt = utterance_stmt.where(Utterance.created_at < until)
    utterances = (await session.execute(utterance_stmt)).scalars().all()

    query_stmt = select(AssistantQuery).where(
        AssistantQuery.venue_id == venue_id,
        AssistantQuery.employee_id == employee_id,
        AssistantQuery.created_at >= since,
    )
    if until is not None:
        query_stmt = query_stmt.where(AssistantQuery.created_at < until)
    queries = (await session.execute(query_stmt)).scalars().all()

    events: list[ShiftEvent] = [
        ShiftEvent(
            kind="utterance",
            at=row.created_at,
            text=row.source_text,
            detail=row.translated_text,
            total_ms=row.total_ms,
            is_help_request=row.recipient_group_id in help_group_ids
            if row.recipient_group_id is not None
            else False,
        )
        for row in utterances
    ]
    events += [
        ShiftEvent(
            kind="assistant_query",
            at=row.created_at,
            text=row.query_text,
            detail=row.answer_text,
            total_ms=row.total_ms,
            menu_item_found=row.menu_item_found,
        )
        for row in queries
    ]
    return events


async def employee_shifts(
    session: AsyncSession, venue_id: int, employee_id: int, *, since: datetime
) -> list[ShiftSummary]:
    """Список смен сотрудника (без транскрипта событий в каждой — только сводка).
    Для детального просмотра одной смены см. shift_detail."""
    events = await load_shift_events(session, venue_id, employee_id, since=since)
    summaries = group_events_into_shifts(events, employee_id=employee_id)
    return [
        ShiftSummary(
            shift_date=s.shift_date,
            employee_id=s.employee_id,
            started_at=s.started_at,
            ended_at=s.ended_at,
            utterances_count=s.utterances_count,
            assistant_queries_count=s.assistant_queries_count,
            help_requests=s.help_requests,
            response_sec=s.response_sec,
            events=[],  # список смен — сводка, транскрипт отдаёт shift_detail
        )
        for s in summaries
    ]


async def shift_detail(
    session: AsyncSession, venue_id: int, employee_id: int, shift_date: date
) -> ShiftSummary | None:
    """Одна смена с полным транскриптом событий (детали "диалога", п.3 задания)."""
    since = datetime.combine(shift_date, datetime.min.time(), tzinfo=UTC)
    until = since + timedelta(days=1)
    # created_at в БД — timestamptz; границы дня считаем в UTC (см. предупреждение
    # в докстринге ShiftSummary про приближение к границе смены).
    events = await load_shift_events(session, venue_id, employee_id, since=since, until=until)
    if not events:
        return None
    summaries = group_events_into_shifts(events, employee_id=employee_id)
    return summaries[0]


# --- FAQ: агрегация реальных вопросов к ассистенту (п.4 задания) ----------------


def normalize_query_text(text: str) -> str:
    """Нормализация вопроса для группировки в FAQ — без регистра и лишних
    пробелов, чтобы разные формулировки одного вопроса схлопнулись в одну
    строку ("Что в лагмане?" и "что в лагмане" — один и тот же вопрос)."""
    return " ".join(text.strip().casefold().split())


@dataclass(frozen=True)
class FaqQuestionRow:
    """Один сырой вопрос к ассистенту — вход для агрегации FAQ."""

    query_text: str
    menu_item_found: bool
    total_ms: int | None
    created_at: datetime


@dataclass(frozen=True)
class FaqTopQuestion:
    """Часто задаваемый вопрос с реальной статистикой (никаких conversion —
    у нас нет продаж, поле сознательно не заводим)."""

    question: str
    count: int
    trend_percent: float | None  # None — нет данных за предыдущее окно для сравнения
    avg_response_sec: float | None
    ever_answered: bool
    last_asked_at: datetime


def aggregate_top_questions(
    rows: list[FaqQuestionRow], *, now: datetime, trend_window_days: int = 7
) -> list[FaqTopQuestion]:
    """Сгруппировать вопросы по нормализованному тексту: частота, тренд (это
    окно к предыдущему такому же) и среднее время ответа. Отсортировано по
    убыванию частоты — самое частое первым."""
    recent_cutoff = now - timedelta(days=trend_window_days)
    prev_cutoff = now - timedelta(days=2 * trend_window_days)

    groups: dict[str, list[FaqQuestionRow]] = defaultdict(list)
    for row in rows:
        groups[normalize_query_text(row.query_text)].append(row)

    result: list[FaqTopQuestion] = []
    for question, group in groups.items():
        recent = sum(1 for r in group if r.created_at >= recent_cutoff)
        previous = sum(1 for r in group if prev_cutoff <= r.created_at < recent_cutoff)
        trend = None if previous == 0 else round((recent - previous) / previous * 100, 1)
        response_values = [r.total_ms for r in group if r.total_ms is not None]
        result.append(
            FaqTopQuestion(
                question=question,
                count=len(group),
                trend_percent=trend,
                avg_response_sec=avg_response_seconds(response_values),
                ever_answered=any(r.menu_item_found for r in group),
                last_asked_at=max(r.created_at for r in group),
            )
        )
    result.sort(key=lambda item: item.count, reverse=True)
    return result


@dataclass(frozen=True)
class FaqGap:
    """Вопрос, на который ассистент не нашёл ответа в меню — дыра в данных
    точки (техкарта/меню), самое ценное для управляющего (см. задание лупа)."""

    question: str
    miss_count: int
    last_asked_at: datetime
    sample_query: str


def aggregate_gaps(rows: list[FaqQuestionRow]) -> list[FaqGap]:
    """Только неотвеченные вопросы (menu_item_found=False), сгруппированные и
    отсортированные по частоте промаха — от самого частого."""
    groups: dict[str, list[FaqQuestionRow]] = defaultdict(list)
    for row in rows:
        if row.menu_item_found:
            continue
        groups[normalize_query_text(row.query_text)].append(row)

    gaps = [
        FaqGap(
            question=question,
            miss_count=len(group),
            last_asked_at=max(r.created_at for r in group),
            sample_query=group[0].query_text,
        )
        for question, group in groups.items()
    ]
    gaps.sort(key=lambda item: item.miss_count, reverse=True)
    return gaps


async def faq_rows(
    session: AsyncSession, venue_id: int, *, since: datetime
) -> list[FaqQuestionRow]:
    """Сырые вопросы к ассистенту точки за окно — вход для aggregate_top_questions
    и aggregate_gaps. Окно должно охватывать минимум 2*trend_window_days, чтобы
    тренд FAQ можно было посчитать (иначе trend_percent честно уйдёт в None)."""
    rows = (
        await session.execute(
            select(
                AssistantQuery.query_text,
                AssistantQuery.menu_item_found,
                AssistantQuery.total_ms,
                AssistantQuery.created_at,
            ).where(
                AssistantQuery.venue_id == venue_id,
                AssistantQuery.created_at >= since,
            )
        )
    ).all()
    return [
        FaqQuestionRow(
            query_text=row[0], menu_item_found=row[1], total_ms=row[2], created_at=row[3]
        )
        for row in rows
    ]


# --- Тесты обучения: оценка результата (п.5 задания) ----------------------------


def score_test(answers: list[int], correct_indices: list[int]) -> int:
    """Процент правильных ответов (округление к ближайшему целому).

    Несовпадение длин — ValueError: сотрудник должен ответить на каждый
    вопрос ровно один раз, ни меньше, ни больше (проверяется в API до вызова).
    """
    if len(answers) != len(correct_indices):
        raise ValueError("Число ответов не совпадает с числом вопросов теста")
    if not correct_indices:
        return 0
    correct = sum(
        1 for given, expected in zip(answers, correct_indices, strict=True) if given == expected
    )
    return round(correct / len(correct_indices) * 100)
