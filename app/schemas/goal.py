from pydantic import BaseModel, Field


class GoalIn(BaseModel):
    """Постановка цели сотруднику (обычно от РОПа)."""

    employee_id: int
    title: str = Field(min_length=1, max_length=200)
    target: int = Field(default=1, ge=1)
    reward_points: int = Field(default=10, ge=0)


class GoalOut(BaseModel):
    id: int
    employee_id: int
    title: str
    target: int
    progress: int
    reward_points: int
    done: bool

    model_config = {"from_attributes": True}
