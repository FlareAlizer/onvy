"""REST статистики/смен сотрудника и агрегации FAQ (задание лупа, пп.2-4).

Права: ростер точки и FAQ-агрегации — только управляющий; статистику и смены
сотрудник видит сам, чужие — тоже только управляющий (та же идиома self-or-
manager, что app/api/kpi.py).
"""

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.menu import require_own_venue
from app.db import get_session
from app.db.models.employee import Employee
from app.deps import CurrentEmployee, require_employee, require_manager
from app.schemas.staff import (
    EmployeeOut,
    EmployeeStatsOut,
    FaqGapOut,
    FaqTopQuestionOut,
    ShiftDetailOut,
    ShiftEventOut,
    ShiftSummaryOut,
)
from app.services import stats

router = APIRouter(prefix="/venues/{venue_id}", tags=["staff"])


def _require_self_or_manager(current: CurrentEmployee, employee_id: int) -> None:
    if current.role != "manager" and current.id != employee_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Можно смотреть только свои данные")


@router.get("/staff", response_model=list[EmployeeOut])
async def list_staff(
    venue_id: int,
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> list[EmployeeOut]:
    """Ростер точки — кабинет руководителя."""
    require_own_venue(current, venue_id)
    rows = (
        (
            await db.execute(
                select(Employee).where(Employee.venue_id == venue_id, Employee.deleted_at.is_(None))
            )
        )
        .scalars()
        .all()
    )
    return [
        EmployeeOut(
            id=e.id,
            name=e.name,
            nickname=e.nickname,
            role=e.role,
            language=e.language,
            is_active=e.is_active,
            hired_at=e.hired_at,
        )
        for e in rows
    ]


@router.get("/staff/{employee_id}/stats", response_model=EmployeeStatsOut)
async def employee_stats_endpoint(
    venue_id: int,
    employee_id: int,
    days: int = Query(default=7, ge=1, le=90),
    current: CurrentEmployee = Depends(require_employee),
    db: AsyncSession = Depends(get_session),
) -> EmployeeStatsOut:
    """EmployeeStats фронта — честная версия (задание, п.2): revenue/avg_check/
    conversion/script_compliance здесь нет, см. app/schemas/staff.py."""
    require_own_venue(current, venue_id)
    _require_self_or_manager(current, employee_id)
    since = datetime.now(UTC) - timedelta(days=days)
    result = await stats.employee_stats(db, venue_id, employee_id, since=since, period_days=days)
    return EmployeeStatsOut(
        employee_id=result.employee_id,
        period_days=result.period_days,
        dialogs=result.dialogs,
        response_sec=result.response_sec,
        autonomy_percent=result.autonomy_percent,
        help_requests=result.help_requests,
    )


@router.get("/staff/{employee_id}/shifts", response_model=list[ShiftSummaryOut])
async def employee_shifts_endpoint(
    venue_id: int,
    employee_id: int,
    days: int = Query(default=14, ge=1, le=90),
    current: CurrentEmployee = Depends(require_employee),
    db: AsyncSession = Depends(get_session),
) -> list[ShiftSummaryOut]:
    """Список смен сотрудника — честная замена ленте "диалогов" фронта (задание,
    п.3): у нас нет понятия обслуживания одного гостя, есть поток реплик/вопросов
    за смену. Подробности одной смены — GET .../shifts/{shift_date}."""
    require_own_venue(current, venue_id)
    _require_self_or_manager(current, employee_id)
    since = datetime.now(UTC) - timedelta(days=days)
    shifts = await stats.employee_shifts(db, venue_id, employee_id, since=since)
    return [
        ShiftSummaryOut(
            shift_date=s.shift_date,
            employee_id=s.employee_id,
            started_at=s.started_at,
            ended_at=s.ended_at,
            utterances_count=s.utterances_count,
            assistant_queries_count=s.assistant_queries_count,
            help_requests=s.help_requests,
            response_sec=s.response_sec,
        )
        for s in shifts
    ]


@router.get("/staff/{employee_id}/shifts/{shift_date}", response_model=ShiftDetailOut)
async def employee_shift_detail_endpoint(
    venue_id: int,
    employee_id: int,
    shift_date: date,
    current: CurrentEmployee = Depends(require_employee),
    db: AsyncSession = Depends(get_session),
) -> ShiftDetailOut:
    """Детали одной смены с транскриптом — "детали диалога" фронта (задание, п.3).
    wave/moments сознательно отсутствуют, а не отданы пустыми под видом реальных
    данных — см. app/schemas/staff.py ShiftDetailOut."""
    require_own_venue(current, venue_id)
    _require_self_or_manager(current, employee_id)
    detail = await stats.shift_detail(db, venue_id, employee_id, shift_date)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="За эту дату событий нет")
    return ShiftDetailOut(
        shift_date=detail.shift_date,
        employee_id=detail.employee_id,
        started_at=detail.started_at,
        ended_at=detail.ended_at,
        utterances_count=detail.utterances_count,
        assistant_queries_count=detail.assistant_queries_count,
        help_requests=detail.help_requests,
        response_sec=detail.response_sec,
        events=[
            ShiftEventOut(
                kind=e.kind,
                at=e.at,
                text=e.text,
                detail=e.detail,
                total_ms=e.total_ms,
                menu_item_found=e.menu_item_found,
                is_help_request=e.is_help_request,
            )
            for e in detail.events
        ],
    )


@router.get("/faq/top-questions", response_model=list[FaqTopQuestionOut])
async def faq_top_questions(
    venue_id: int,
    days: int = Query(default=30, ge=1, le=180),
    limit: int = Query(default=20, ge=1, le=100),
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> list[FaqTopQuestionOut]:
    """Частые вопросы официантов к ассистенту — база знаний FAQ, реальная
    агрегация assistant_queries (задание, п.4)."""
    require_own_venue(current, venue_id)
    since = datetime.now(UTC) - timedelta(days=days)
    rows = await stats.faq_rows(db, venue_id, since=since)
    top = stats.aggregate_top_questions(rows, now=datetime.now(UTC))[:limit]
    return [
        FaqTopQuestionOut(
            question=item.question,
            count=item.count,
            trend_percent=item.trend_percent,
            avg_response_sec=item.avg_response_sec,
            ever_answered=item.ever_answered,
            last_asked_at=item.last_asked_at,
        )
        for item in top
    ]


@router.get("/faq/gaps", response_model=list[FaqGapOut])
async def faq_gaps(
    venue_id: int,
    days: int = Query(default=30, ge=1, le=180),
    limit: int = Query(default=20, ge=1, le=100),
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> list[FaqGapOut]:
    """Вопросы, на которые ассистент не нашёл ответа в меню — самое ценное для
    управляющего: показывает дыры в техкарте/меню (задание, п.4)."""
    require_own_venue(current, venue_id)
    since = datetime.now(UTC) - timedelta(days=days)
    rows = await stats.faq_rows(db, venue_id, since=since)
    gaps = stats.aggregate_gaps(rows)[:limit]
    return [
        FaqGapOut(
            question=item.question,
            miss_count=item.miss_count,
            last_asked_at=item.last_asked_at,
            sample_query=item.sample_query,
        )
        for item in gaps
    ]
