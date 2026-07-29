"""Схемы KPI-целей сотрудникам (кабинет руководителя/сотрудника).

metric/period валидируются здесь же (а не только CHECK-констрейнтом в БД),
чтобы неверное значение отвечало 422 с понятным сообщением, а не 500 из-за
нарушения констрейнта на INSERT.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.db.models.enums import KPI_METRICS, KPI_PERIODS


class KpiSetIn(BaseModel):
    """Тело POST при постановке цели одному сотруднику."""

    metric: str = Field(description=f"Один из: {', '.join(KPI_METRICS)}")
    target: Decimal = Field(ge=0)
    period: str = Field(description=f"Один из: {', '.join(KPI_PERIODS)}")
    note: str | None = Field(default=None, max_length=300)

    @field_validator("metric")
    @classmethod
    def _metric_known(cls, value: str) -> str:
        if value not in KPI_METRICS:
            raise ValueError(f"metric должен быть одним из {KPI_METRICS}")
        return value

    @field_validator("period")
    @classmethod
    def _period_known(cls, value: str) -> str:
        if value not in KPI_PERIODS:
            raise ValueError(f"period должен быть одним из {KPI_PERIODS}")
        return value


class KpiSetForAllIn(KpiSetIn):
    """Тело POST при постановке одной и той же цели всем активным сотрудникам точки."""


class KpiOut(BaseModel):
    """Цель с прогрессом. `current`/`progress_percent` — None значит "по этой
    метрике за окно ещё нет данных", а не 0: см. app/services/stats.py."""

    id: int
    employee_id: int
    metric: str
    target: Decimal
    current: float | None
    progress_percent: float | None
    period: str
    period_start: date
    period_end: date
    set_by_employee_id: int
    note: str | None
