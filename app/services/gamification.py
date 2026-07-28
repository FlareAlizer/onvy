"""Геймификация: начисление очков за активность и прогресс по целям.

Очки — простой мотивационный слой ЛК сотрудника (в отличие от диктофонов-
«ревизоров»). Значения вынесены в константы, чтобы легко калибровать.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.goal import Goal

# Сколько очков за какое действие.
POINTS_ASSISTANT_FOUND = 2  # ассистент помог (нашёл ответ)
POINTS_ASSISTANT_MISS = 1  # спросил, но не нашлось (всё равно вовлечён)
POINTS_MESSAGE = 1  # реплика по связи


async def award_points(db: AsyncSession, employee_id: int | None, points: int) -> None:
    """Начислить очки сотруднику (если он существует)."""
    if employee_id is None or points <= 0:
        return
    employee = await db.get(Employee, employee_id)
    if employee is not None:
        employee.points += points
        await db.flush()


async def advance_goal(db: AsyncSession, goal: Goal, by: int = 1) -> Goal:
    """Продвинуть цель; при достижении target — закрыть и начислить награду.

    Начисление награды идемпотентно: повторный вызов на выполненной цели ничего
    не добавляет.
    """
    if goal.done:
        return goal
    goal.progress = min(goal.target, goal.progress + by)
    if goal.progress >= goal.target:
        goal.done = True
        await award_points(db, goal.employee_id, goal.reward_points)
    await db.flush()
    return goal
