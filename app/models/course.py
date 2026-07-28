from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Course(Base):
    """Микро-курс обучения (шаги: контент и квизы), генерируется YandexGPT."""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(60), default="Sales")
    steps_json: Mapped[str] = mapped_column(Text, default="[]")  # шаги курса (JSON)


class CourseProgress(Base):
    """Прогресс сотрудника по курсу (0–100)."""

    __tablename__ = "course_progress"
    __table_args__ = (UniqueConstraint("employee_id", "course_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    progress: Mapped[int] = mapped_column(default=0)
