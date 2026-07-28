from pydantic import BaseModel

from app.schemas.goal import GoalOut


class EmployeeStats(BaseModel):
    """Сводка по сотруднику для ЛК сотрудника и дашборда РОПа."""

    employee_id: int
    name: str
    role: str
    language: str
    points: int
    online: bool
    assistant_queries: int
    messages_sent: int
    goals: list[GoalOut]


class TopQuery(BaseModel):
    query: str
    count: int


class RopDashboard(BaseModel):
    """Дашборд РОПа: команда, кто онлайн, аналитика диалогов."""

    online_ids: list[int]
    team: list[EmployeeStats]
    total_assistant_queries: int
    assistant_hit_rate: float  # доля запросов, на которые нашёлся ответ
    total_messages: int
    top_queries: list[TopQuery]
