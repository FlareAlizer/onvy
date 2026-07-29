"""Схемы тестов обучения (кабинет руководителя/сотрудника).

Ключевая граница честности: сотрудник, ещё не прошедший тест, не должен
видеть correct_index/explain (TestQuestionForEmployeeOut) — иначе тест не
проверяет знания, а проверяет умение читать JSON. Правильные ответы
появляются только в разборе после отправки (TestResultOut.review).
"""

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.db.models.enums import TEST_SOURCES


class TestQuestionIn(BaseModel):
    """Один вопрос при создании теста — без id, порядок = позиция в списке questions."""

    question: str = Field(min_length=1)
    options: list[str] = Field(min_length=2)
    correct_index: int = Field(ge=0)
    explain: str | None = None
    source: str | None = None

    @model_validator(mode="after")
    def _correct_index_in_range(self) -> "TestQuestionIn":
        if self.correct_index >= len(self.options):
            raise ValueError("correct_index должен указывать на существующий вариант ответа")
        return self


class TestCreateIn(BaseModel):
    """Тело POST при создании теста. Вопросы приходят готовыми — генерация не
    в этом лупе (задание, п.5)."""

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    source: str = Field(description=f"Один из: {', '.join(TEST_SOURCES)}")
    source_detail: str = Field(default="", max_length=500)
    deadline: date | None = None
    pass_score: int = Field(default=70, ge=0, le=100)
    questions: list[TestQuestionIn] = Field(min_length=1)

    @field_validator("source")
    @classmethod
    def _source_known(cls, value: str) -> str:
        if value not in TEST_SOURCES:
            raise ValueError(f"source должен быть одним из {TEST_SOURCES}")
        return value


class TestAssignIn(BaseModel):
    """Тело POST при назначении теста списку сотрудников."""

    employee_ids: list[int] = Field(min_length=1)


class TestSubmitIn(BaseModel):
    """Тело POST при отправке ответов. Порядок answers — порядок вопросов
    по position (см. TestForEmployeeOut.questions)."""

    answers: list[int] = Field(min_length=1)


# --- Ответы: кабинет руководителя -----------------------------------------------


class TestQuestionOut(BaseModel):
    """Вопрос теста с правильным ответом — только для руководителя."""

    id: int
    position: int
    question: str
    options: list[str]
    correct_index: int
    explain: str | None
    source: str | None


class TestResultSummaryOut(BaseModel):
    """Один результат в списке результатов теста (кабинет руководителя)."""

    employee_id: int
    score_percent: int
    passed: bool
    completed_at: datetime


class TestOut(BaseModel):
    """Тест целиком — кабинет руководителя."""

    id: int
    title: str
    description: str
    source: str
    source_detail: str
    created_at: datetime
    created_by_employee_id: int
    deadline: date | None
    pass_score: int
    questions: list[TestQuestionOut]
    assigned_employee_ids: list[int]
    results: list[TestResultSummaryOut]


# --- Ответы: кабинет сотрудника ---------------------------------------------------


class TestQuestionForEmployeeOut(BaseModel):
    """Вопрос для прохождения — без correct_index/explain (см. докстринг модуля)."""

    id: int
    position: int
    question: str
    options: list[str]


class TestForEmployeeOut(BaseModel):
    """Назначенный тест в кабинете сотрудника."""

    id: int
    title: str
    description: str
    deadline: date | None
    pass_score: int
    questions: list[TestQuestionForEmployeeOut]
    completed: bool
    score_percent: int | None


class TestQuestionReviewOut(BaseModel):
    """Вопрос в разборе результата — доступен только после прохождения."""

    id: int
    position: int
    question: str
    options: list[str]
    correct_index: int
    given_index: int
    is_correct: bool
    explain: str | None


class TestResultOut(BaseModel):
    """Результат прохождения — с разбором по каждому вопросу (ответ сразу после submit)."""

    test_id: int
    employee_id: int
    score_percent: int
    passed: bool
    completed_at: datetime
    review: list[TestQuestionReviewOut]
