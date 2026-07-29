"""CRUD целей (KPI) сотрудникам поверх ORM (фронт: интерфейс `Kpi`,
frontend/src/types.ts). Постановка — одному сотруднику или всем сразу
(задание лупа, п.1); текущее значение цели никогда не с потолка — считается
из реальных данных через app/services/stats.py.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.employee import Employee
from app.db.models.kpi import Kpi
from app.services import stats


class KpiServiceError(Exception):
    """Базовая ошибка сервиса KPI."""


class EmployeeNotFoundError(KpiServiceError):
    def __init__(self, employee_id: int) -> None:
        super().__init__(f"Сотрудник {employee_id} не найден на этой точке")
        self.employee_id = employee_id


class KpiNotFoundError(KpiServiceError):
    def __init__(self, kpi_id: int) -> None:
        super().__init__(f"Цель {kpi_id} не найдена на этой точке")
        self.kpi_id = kpi_id


# Метрика KPI -> ключ EmployeeStatsResult (app/services/stats.py). Явная карта,
# а не getattr по имени: опечатка в ключе не должна тихо отдавать None вместо
# ошибки на этапе разработки.
_METRIC_TO_STATS_FIELD = {
    "dialogs": "dialogs",
    "response_sec": "response_sec",
    "autonomy": "autonomy_percent",
    "help_requests": "help_requests",
}


async def _get_owned_employee(session: AsyncSession, venue_id: int, employee_id: int) -> Employee:
    employee = await session.get(Employee, employee_id)
    if employee is None or employee.venue_id != venue_id or employee.deleted_at is not None:
        raise EmployeeNotFoundError(employee_id)
    return employee


async def set_kpi(
    session: AsyncSession,
    *,
    venue_id: int,
    employee_id: int,
    metric: str,
    target: Decimal,
    period: str,
    on_date: date,
    set_by_employee_id: int,
    note: str | None = None,
) -> Kpi:
    """Поставить/обновить цель одному сотруднику. Идемпотентно по (employee,
    metric, period, period_start): повторная постановка на то же окно правит
    ту же строку, а не плодит дубликаты (см. unique-индекс в app/db/models/kpi.py)."""
    await _get_owned_employee(session, venue_id, employee_id)
    period_start, period_end = stats.period_bounds(period, on_date)

    existing = (
        await session.execute(
            select(Kpi).where(
                Kpi.employee_id == employee_id,
                Kpi.metric == metric,
                Kpi.period == period,
                Kpi.period_start == period_start,
            )
        )
    ).scalars().first()

    if existing is not None:
        existing.target = target
        existing.note = note
        existing.set_by_employee_id = set_by_employee_id
        await session.flush()
        await session.refresh(existing)
        return existing

    kpi = Kpi(
        venue_id=venue_id,
        employee_id=employee_id,
        metric=metric,
        target=target,
        period=period,
        period_start=period_start,
        period_end=period_end,
        set_by_employee_id=set_by_employee_id,
        note=note,
    )
    session.add(kpi)
    await session.flush()
    await session.refresh(kpi)
    return kpi


async def set_kpi_for_all(
    session: AsyncSession,
    *,
    venue_id: int,
    metric: str,
    target: Decimal,
    period: str,
    on_date: date,
    set_by_employee_id: int,
    note: str | None = None,
) -> list[Kpi]:
    """Поставить одну и ту же цель всем активным сотрудникам точки разом."""
    employee_ids = (
        await session.execute(
            select(Employee.id).where(
                Employee.venue_id == venue_id,
                Employee.is_active.is_(True),
                Employee.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    return [
        await set_kpi(
            session,
            venue_id=venue_id,
            employee_id=employee_id,
            metric=metric,
            target=target,
            period=period,
            on_date=on_date,
            set_by_employee_id=set_by_employee_id,
            note=note,
        )
        for employee_id in employee_ids
    ]


async def list_kpis(
    session: AsyncSession, venue_id: int, *, employee_id: int | None = None
) -> list[Kpi]:
    """Цели точки, свежие периоды впереди. employee_id=None — все сотрудники
    (кабинет руководителя), иначе — только свои (кабинет сотрудника)."""
    stmt = select(Kpi).where(Kpi.venue_id == venue_id)
    if employee_id is not None:
        stmt = stmt.where(Kpi.employee_id == employee_id)
    stmt = stmt.order_by(Kpi.period_start.desc(), Kpi.employee_id)
    return list((await session.execute(stmt)).scalars().all())


async def get_owned_kpi(session: AsyncSession, venue_id: int, kpi_id: int) -> Kpi:
    kpi = await session.get(Kpi, kpi_id)
    if kpi is None or kpi.venue_id != venue_id:
        raise KpiNotFoundError(kpi_id)
    return kpi


async def current_value(session: AsyncSession, kpi: Kpi) -> float | None:
    """Текущее значение метрики цели за [period_start, period_end] — считается
    из реальных данных смены (app/services/stats.py), никогда не с потолка.
    None — либо метрика без данных за окно (см. autonomy_percent/avg_response_seconds),
    либо (в теории) неизвестный metric — не должно происходить: CHECK-констрейнт
    в БД и Pydantic-схема ограничивают metric значениями из _METRIC_TO_STATS_FIELD.
    """
    since = datetime.combine(kpi.period_start, datetime.min.time(), tzinfo=UTC)
    until = datetime.combine(kpi.period_end, datetime.min.time(), tzinfo=UTC) + timedelta(days=1)
    result = await stats.employee_stats(
        session,
        kpi.venue_id,
        kpi.employee_id,
        since=since,
        until=until,
        period_days=(kpi.period_end - kpi.period_start).days + 1,
    )
    field_name = _METRIC_TO_STATS_FIELD[kpi.metric]
    value = getattr(result, field_name)
    return None if value is None else float(value)
