"""Схемы ростера персонала, статистики сотрудника, смен и FAQ (кабинет
руководителя/сотрудника).

Честность источников (задание лупа): revenue/avg_check/conversion/
script_compliance фронта (EmployeeStats, Dialog из frontend/src/types.ts)
здесь нет — без интеграции с POS их не из чего посчитать. Схемы называют
такие поля отсутствующими явно (unavailable_metrics), а не отдают 0/выдумку
под видом настоящих данных.
"""

from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field


class EmployeeOut(BaseModel):
    """Сотрудник в ростере точки (кабинет руководителя)."""

    id: int
    name: str
    nickname: str | None
    role: str
    language: str
    is_active: bool
    hired_at: datetime


class StaffCreateRequest(BaseModel):
    """Добавить человека в смену.

    Почта необязательна: линейному персоналу она не нужна, им хватает входа по
    PIN — официант вводит его одной рукой, не глядя. Почту заводят тем, кто
    работает через кабинет.
    """

    name: str = Field(min_length=2, max_length=120)
    role: str = Field(description="waiter, kitchen, bar, host или manager")
    language: str = Field(default="ru", description="ru, uz, kk, ky, en или tg")
    nickname: str | None = Field(default=None, max_length=60)
    email: EmailStr | None = None


class StaffAccessOut(BaseModel):
    """Выданные доступы. Показываются ОДИН раз — в базе только argon2id-хеши.

    Посмотреть их повторно нельзя даже управляющему: это не ограничение
    интерфейса, а свойство хранения. Забыли — перевыдайте.
    """

    employee_id: int
    name: str
    nickname: str | None
    role: str
    language: str
    pin: str
    email: str | None = None
    password: str | None = None


# --- Статистика сотрудника (п.2 задания) -----------------------------------------


class EmployeeStatsOut(BaseModel):
    """EmployeeStats фронта, честная версия: dialogs/response_sec/autonomy_percent/
    help_requests считаются из реальных данных (app/services/stats.py).
    revenue/avg_check/conversion/script_compliance сознательно не заводим
    полями — источника (POS) нет, см. докстринг модуля."""

    employee_id: int
    period_days: int
    dialogs: int
    response_sec: float | None
    autonomy_percent: float | None
    help_requests: int
    unavailable_metrics: list[str] = Field(
        default_factory=lambda: ["revenue", "avg_check", "conversion", "script_compliance"],
        description="Метрики фронта, которых нет без интеграции с POS",
    )


# --- Смены сотрудника — замена Dialog фронта (п.3 задания) -----------------------


class ShiftSummaryOut(BaseModel):
    """Сводка одной смены в списке смен сотрудника."""

    shift_date: date
    employee_id: int
    started_at: datetime | None
    ended_at: datetime | None
    utterances_count: int
    assistant_queries_count: int
    help_requests: int
    response_sec: float | None


class ShiftEventOut(BaseModel):
    """Одно событие в транскрипте смены — реплика рации или вопрос к ассистенту."""

    kind: str
    at: datetime
    text: str
    detail: str | None
    total_ms: int | None
    menu_item_found: bool | None
    is_help_request: bool


class ShiftDetailOut(ShiftSummaryOut):
    """Детали одной смены с транскриптом. `wave`/AI-`moments` фронта (Dialog)
    здесь сознательно нет: источника для них нет в этом лупе — отсутствие
    полей честнее пустых списков под видом настоящих данных (задание, п.3)."""

    events: list[ShiftEventOut]


# --- FAQ: агрегация реальных вопросов к ассистенту (п.4 задания) -----------------


class FaqTopQuestionOut(BaseModel):
    """Часто задаваемый вопрос — реальная агрегация assistant_queries.
    trend_percent=None значит "нет данных за предыдущее окно для сравнения",
    не 0%."""

    question: str
    count: int
    trend_percent: float | None
    avg_response_sec: float | None
    ever_answered: bool
    last_asked_at: datetime


class FaqGapOut(BaseModel):
    """Вопрос, на который ассистент не нашёл ответа, — дыра в меню/техкарте."""

    question: str
    miss_count: int
    last_asked_at: datetime
    sample_query: str
