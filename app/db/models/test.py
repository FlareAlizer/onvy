from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import TEST_SOURCES, sql_in
from app.db.models.mixins import TimestampMixin


class Test(TimestampMixin, Base):
    """Тест для обучения персонала (фронт: интерфейс `Test`).

    Генерацию вопросов ИИ этот луп не делает — вопросы приходят готовыми
    (`TestQuestion`, задаются вместе с тестом), здесь только хранение,
    назначение сотрудникам и результаты прохождения.
    """

    __tablename__ = "tests"
    __table_args__ = (
        CheckConstraint(sql_in("source", TEST_SOURCES), name="source_valid"),
        CheckConstraint("pass_score BETWEEN 0 AND 100", name="pass_score_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(20))
    # Что именно послужило источником — например "3 диалога с ошибкой скрипта"
    # или "FAQ: аллергены". Свободный текст, не структура.
    source_detail: Mapped[str] = mapped_column(Text, default="")
    created_by_employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT")
    )
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    pass_score: Mapped[int] = mapped_column(SmallInteger, default=70)


class TestQuestion(Base):
    """Один вопрос теста. Порядок вопросов — `position` (0-based)."""

    __tablename__ = "test_questions"
    __table_args__ = (
        CheckConstraint("correct_index >= 0", name="correct_index_non_negative"),
        UniqueConstraint("test_id", "position", name="uq_test_questions_test_position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(SmallInteger)
    question: Mapped[str] = mapped_column(Text)
    # Варианты ответа — список строк. JSONB, а не отдельная таблица: порядок
    # вариантов значим (correct_index — индекс в этом же списке), и вопросов
    # мало на тест — реляционная связка здесь усложнила бы без пользы.
    options: Mapped[list[str]] = mapped_column(JSONB)
    correct_index: Mapped[int] = mapped_column(SmallInteger)
    explain: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Из какого раздела базы знаний/типа ошибки взят вопрос — для фронта
    # (TestQuestion.source), свободный текст.
    source: Mapped[str | None] = mapped_column(Text, nullable=True)


class TestAssignment(Base):
    """Назначение теста сотруднику. Составной PK — сотруднику нельзя назначить
    один и тот же тест дважды (повторное назначение в сервисе — no-op)."""

    __tablename__ = "test_assignments"
    __table_args__ = (Index("ix_test_assignments_employee", "employee_id"),)

    test_id: Mapped[int] = mapped_column(
        ForeignKey("tests.id", ondelete="CASCADE"), primary_key=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True
    )
    assigned_by_employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT")
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TestResult(Base):
    """Результат прохождения. Один результат на (test, employee) — повторная
    попытка после уже сохранённого результата отклоняется в сервисе (409):
    иначе результат теряет смысл контроля знаний, если его можно пересдать
    молча до нужного числа.
    """

    __tablename__ = "test_results"
    __table_args__ = (
        CheckConstraint("score_percent BETWEEN 0 AND 100", name="score_percent_range"),
        UniqueConstraint("test_id", "employee_id", name="uq_test_results_test_employee"),
        Index("ix_test_results_employee", "employee_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"))
    score_percent: Mapped[int] = mapped_column(SmallInteger)
    # Выбранные варианты по позиции вопроса — для разбора ошибок вместе с
    # explain/correct_index. Nullable: место на будущее (импорт результата
    # без сырых ответов), сейчас submit всегда его заполняет.
    answers: Mapped[list[int] | None] = mapped_column(JSONB, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
