from pydantic import BaseModel, Field

from app.models.employee import Role


class EmployeeIn(BaseModel):
    """Данные для создания сотрудника."""

    name: str = Field(min_length=1, max_length=120)
    role: Role = Role.employee
    language: str = Field(default="ru", min_length=2, max_length=8)
    department_id: int | None = Field(
        default=None, description="Отдел; если не задан — дефолтный демо-отдел"
    )


class EmployeeUpdate(BaseModel):
    """Изменение профиля сотрудником (язык выбирается в личном кабинете)."""

    language: str | None = Field(default=None, min_length=2, max_length=8)
    name: str | None = Field(default=None, min_length=1, max_length=120)


class EmployeeOut(BaseModel):
    """Сотрудник в ответах API."""

    id: int
    name: str
    role: Role
    language: str
    department_id: int | None

    model_config = {"from_attributes": True}
