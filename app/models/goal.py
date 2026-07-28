from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Goal(Base):
    """Цель сотрудника (геймификация ЛК): прогресс к целевому значению."""

    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    target: Mapped[int] = mapped_column(default=1)  # целевое значение
    progress: Mapped[int] = mapped_column(default=0)  # текущий прогресс
    reward_points: Mapped[int] = mapped_column(default=10)  # очки за выполнение
    done: Mapped[bool] = mapped_column(default=False)
