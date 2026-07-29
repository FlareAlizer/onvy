"""REST целей (KPI) сотрудникам (задание лупа, п.1): управляющий ставит цель
одному сотруднику или всем сразу; текущее значение и прогресс считаются из
реальных данных смены (app/services/stats.py), никогда не с потолка.

Права: ставить цель (одному/всем) и смотреть чужие — только управляющий;
свою цель может посмотреть и сам сотрудник (require_own_venue + сверка
employee_id с current.id).
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.menu import require_own_venue
from app.db import get_session
from app.db.models.kpi import Kpi
from app.deps import CurrentEmployee, require_employee, require_manager
from app.schemas.kpi import KpiOut, KpiSetForAllIn, KpiSetIn
from app.services import kpi as kpi_service
from app.services import stats

router = APIRouter(prefix="/venues/{venue_id}", tags=["kpi"])


def _require_self_or_manager(current: CurrentEmployee, employee_id: int) -> None:
    if current.role != "manager" and current.id != employee_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Можно смотреть только свою цель")


async def _map_kpi(db: AsyncSession, kpi: Kpi) -> KpiOut:
    current_value = await kpi_service.current_value(db, kpi)
    progress = (
        stats.kpi_progress_percent(current_value, kpi.target) if current_value is not None else None
    )
    return KpiOut(
        id=kpi.id,
        employee_id=kpi.employee_id,
        metric=kpi.metric,
        target=kpi.target,
        current=current_value,
        progress_percent=progress,
        period=kpi.period,
        period_start=kpi.period_start,
        period_end=kpi.period_end,
        set_by_employee_id=kpi.set_by_employee_id,
        note=kpi.note,
    )


@router.post(
    "/employees/{employee_id}/kpi", response_model=KpiOut, status_code=status.HTTP_201_CREATED
)
async def set_employee_kpi(
    venue_id: int,
    employee_id: int,
    payload: KpiSetIn,
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> KpiOut:
    """Поставить/обновить цель одному сотруднику. Идемпотентно на окно периода —
    повторный вызов на тот же (метрика, период) правит ту же цель (см.
    app/services/kpi.py set_kpi)."""
    require_own_venue(current, venue_id)
    try:
        kpi = await kpi_service.set_kpi(
            db,
            venue_id=venue_id,
            employee_id=employee_id,
            metric=payload.metric,
            target=payload.target,
            period=payload.period,
            on_date=datetime.now(UTC).date(),
            set_by_employee_id=current.id,
            note=payload.note,
        )
    except kpi_service.EmployeeNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await db.commit()
    return await _map_kpi(db, kpi)


@router.post("/kpi/bulk", response_model=list[KpiOut], status_code=status.HTTP_201_CREATED)
async def set_kpi_for_all_employees(
    venue_id: int,
    payload: KpiSetForAllIn,
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> list[KpiOut]:
    """Поставить одну и ту же цель всем активным сотрудникам точки разом."""
    require_own_venue(current, venue_id)
    kpis = await kpi_service.set_kpi_for_all(
        db,
        venue_id=venue_id,
        metric=payload.metric,
        target=payload.target,
        period=payload.period,
        on_date=datetime.now(UTC).date(),
        set_by_employee_id=current.id,
        note=payload.note,
    )
    await db.commit()
    return [await _map_kpi(db, kpi) for kpi in kpis]


@router.get("/kpi", response_model=list[KpiOut])
async def list_all_kpis(
    venue_id: int,
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> list[KpiOut]:
    """Все цели точки — кабинет руководителя."""
    require_own_venue(current, venue_id)
    kpis = await kpi_service.list_kpis(db, venue_id)
    return [await _map_kpi(db, kpi) for kpi in kpis]


@router.get("/employees/{employee_id}/kpi", response_model=list[KpiOut])
async def list_employee_kpis(
    venue_id: int,
    employee_id: int,
    current: CurrentEmployee = Depends(require_employee),
    db: AsyncSession = Depends(get_session),
) -> list[KpiOut]:
    """Цели одного сотрудника — свои видит сам сотрудник, чужие — только управляющий."""
    require_own_venue(current, venue_id)
    _require_self_or_manager(current, employee_id)
    kpis = await kpi_service.list_kpis(db, venue_id, employee_id=employee_id)
    return [await _map_kpi(db, kpi) for kpi in kpis]
