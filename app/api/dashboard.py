"""Кабинеты: дашборд РОПа (команда, онлайн, аналитика) и сводка сотрудника."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import require_api_key
from app.models.assistant_log import AssistantLog
from app.models.employee import Employee
from app.models.goal import Goal
from app.models.message import Message
from app.schemas.dashboard import EmployeeStats, RopDashboard, TopQuery
from app.schemas.goal import GoalOut
from app.services.comms import manager

router = APIRouter(tags=["dashboard"], dependencies=[Depends(require_api_key)])


async def _counts_by_employee(db: AsyncSession, column, model) -> dict[int, int]:
    """Сгруппировать количество строк model по столбцу-владельцу (employee)."""
    result = await db.execute(select(column, func.count()).group_by(column))
    return {row[0]: row[1] for row in result.all() if row[0] is not None}


async def _employee_stats(
    db: AsyncSession,
    employee: Employee,
    query_counts: dict[int, int],
    message_counts: dict[int, int],
) -> EmployeeStats:
    goals = (await db.execute(select(Goal).where(Goal.employee_id == employee.id))).scalars().all()
    return EmployeeStats(
        employee_id=employee.id,
        name=employee.name,
        role=employee.role.value,
        language=employee.language,
        points=employee.points,
        online=manager.is_online(employee.id),
        assistant_queries=query_counts.get(employee.id, 0),
        messages_sent=message_counts.get(employee.id, 0),
        goals=[GoalOut.model_validate(g) for g in goals],
    )


@router.get("/dashboard/rop", response_model=RopDashboard)
async def rop_dashboard(db: AsyncSession = Depends(get_session)) -> RopDashboard:
    """Сводный дашборд РОПа: кто онлайн, активность и аналитика диалогов."""
    employees = (await db.execute(select(Employee))).scalars().all()
    query_counts = await _counts_by_employee(db, AssistantLog.employee_id, AssistantLog)
    message_counts = await _counts_by_employee(db, Message.sender_id, Message)

    team = [await _employee_stats(db, e, query_counts, message_counts) for e in employees]

    total_queries = (await db.execute(select(func.count()).select_from(AssistantLog))).scalar() or 0
    total_hits = (
        await db.execute(
            select(func.count()).select_from(AssistantLog).where(AssistantLog.found.is_(True))
        )
    ).scalar() or 0
    total_messages = (await db.execute(select(func.count()).select_from(Message))).scalar() or 0

    top_rows = await db.execute(
        select(AssistantLog.query_text, func.count().label("c"))
        .group_by(AssistantLog.query_text)
        .order_by(func.count().desc())
        .limit(5)
    )
    top_queries = [TopQuery(query=r[0], count=r[1]) for r in top_rows.all() if r[0].strip()]

    return RopDashboard(
        online_ids=manager.online_ids(),
        team=team,
        total_assistant_queries=total_queries,
        assistant_hit_rate=round(total_hits / total_queries, 3) if total_queries else 0.0,
        total_messages=total_messages,
        top_queries=top_queries,
    )


@router.get("/dashboard/employee/{employee_id}", response_model=EmployeeStats)
async def employee_dashboard(
    employee_id: int, db: AsyncSession = Depends(get_session)
) -> EmployeeStats:
    """Личный кабинет сотрудника: очки, цели, активность."""
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    query_counts = await _counts_by_employee(db, AssistantLog.employee_id, AssistantLog)
    message_counts = await _counts_by_employee(db, Message.sender_id, Message)
    return await _employee_stats(db, employee, query_counts, message_counts)
