import enum

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Role(enum.StrEnum):
    """Роль сотрудника в магазине."""

    employee = "employee"  # линейный сотрудник
    rop = "rop"  # руководитель отдела продаж (РОП)


class Employee(Base):
    """Сотрудник магазина — владелец гарнитуры/приложения Onvy."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[Role] = mapped_column(default=Role.employee)
    # Язык сотрудника (ISO 639-1): на нём он говорит и слышит подсказки/перевод.
    language: Mapped[str] = mapped_column(String(8), default="ru")
    # Отдел, к которому подключён сотрудник (для broadcast по отделу).
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id"), nullable=True, index=True
    )
    # Геймификация: очки за активность (запросы к ассистенту, реплики, цели).
    points: Mapped[int] = mapped_column(default=0)
