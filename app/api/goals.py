from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import require_api_key
from app.models.employee import Employee
from app.models.goal import Goal
from app.schemas.goal import GoalIn, GoalOut
from app.services import gamification

router = APIRouter(tags=["goals"], dependencies=[Depends(require_api_key)])


@router.post("/goals", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
async def create_goal(payload: GoalIn, db: AsyncSession = Depends(get_session)) -> Goal:
    """Поставить цель сотруднику (обычно действие РОПа)."""
    if await db.get(Employee, payload.employee_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    goal = Goal(
        employee_id=payload.employee_id,
        title=payload.title,
        target=payload.target,
        reward_points=payload.reward_points,
    )
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return goal


@router.get("/goals/employee/{employee_id}", response_model=list[GoalOut])
async def list_goals(employee_id: int, db: AsyncSession = Depends(get_session)) -> list[Goal]:
    """Цели сотрудника."""
    result = await db.execute(select(Goal).where(Goal.employee_id == employee_id))
    return list(result.scalars().all())


@router.post("/goals/{goal_id}/advance", response_model=GoalOut)
async def advance_goal(goal_id: int, by: int = 1, db: AsyncSession = Depends(get_session)) -> Goal:
    """Продвинуть цель; при достижении — закрыть и начислить награду очками."""
    goal = await db.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Цель не найдена")
    await gamification.advance_goal(db, goal, by)
    await db.commit()
    await db.refresh(goal)
    return goal
