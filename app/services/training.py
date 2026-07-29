"""CRUD тестов обучения поверх ORM (фронт: интерфейсы `Test`/`TestQuestion`,
frontend/src/types.ts). Генерация вопросов ИИ — не в этом лупе (задание,
п.5): вопросы приходят готовыми, здесь только хранение, назначение
сотрудникам, прохождение и результат.

Сознательно без SQLAlchemy relationship()/lazy-load (как и остальной домен —
см. app/services/menu.py): вопросы/назначения/результаты теста собираются
явными select() в TestDetail, а не обходом ORM-графа.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.employee import Employee
from app.db.models.test import Test, TestAssignment, TestQuestion, TestResult
from app.services.stats import score_test


class TrainingServiceError(Exception):
    """Базовая ошибка сервиса тестов обучения."""


class TestNotFoundError(TrainingServiceError):
    def __init__(self, test_id: int) -> None:
        super().__init__(f"Тест {test_id} не найден на этой точке")
        self.test_id = test_id


class EmployeeNotFoundError(TrainingServiceError):
    def __init__(self, employee_id: int) -> None:
        super().__init__(f"Сотрудник {employee_id} не найден на этой точке")
        self.employee_id = employee_id


class NotAssignedError(TrainingServiceError):
    """Сотрудник пытается пройти тест, который ему не назначали."""

    def __init__(self, test_id: int, employee_id: int) -> None:
        super().__init__(f"Тест {test_id} не назначен сотруднику {employee_id}")
        self.test_id = test_id
        self.employee_id = employee_id


class AlreadyCompletedError(TrainingServiceError):
    """Повторная попытка после уже сохранённого результата — не тихая
    перезапись: результат контроля знаний теряет смысл, если его можно
    пересдавать молча."""

    def __init__(self, test_id: int, employee_id: int) -> None:
        super().__init__(f"Сотрудник {employee_id} уже прошёл тест {test_id}")
        self.test_id = test_id
        self.employee_id = employee_id


@dataclass(frozen=True)
class QuestionIn:
    """Один вопрос при создании теста — без id, порядок = позиция в списке."""

    question: str
    options: list[str]
    correct_index: int
    explain: str | None = None
    source: str | None = None


@dataclass(frozen=True)
class TestDetail:
    """Тест целиком: вопросы (по порядку), кому назначен, чьи результаты есть."""

    test: Test
    questions: list[TestQuestion]
    assigned_employee_ids: list[int]
    results: list[TestResult]


async def _get_owned_employee(session: AsyncSession, venue_id: int, employee_id: int) -> Employee:
    employee = await session.get(Employee, employee_id)
    if employee is None or employee.venue_id != venue_id or employee.deleted_at is not None:
        raise EmployeeNotFoundError(employee_id)
    return employee


async def _fetch_detail(session: AsyncSession, venue_id: int, test: Test) -> TestDetail:
    questions = (
        (
            await session.execute(
                select(TestQuestion)
                .where(TestQuestion.test_id == test.id)
                .order_by(TestQuestion.position)
            )
        )
        .scalars()
        .all()
    )
    assigned_ids = (
        (
            await session.execute(
                select(TestAssignment.employee_id).where(TestAssignment.test_id == test.id)
            )
        )
        .scalars()
        .all()
    )
    results = (
        (await session.execute(select(TestResult).where(TestResult.test_id == test.id)))
        .scalars()
        .all()
    )
    return TestDetail(
        test=test,
        questions=list(questions),
        assigned_employee_ids=list(assigned_ids),
        results=list(results),
    )


async def create_test(
    session: AsyncSession,
    venue_id: int,
    *,
    title: str,
    description: str,
    source: str,
    source_detail: str,
    created_by_employee_id: int,
    deadline: date | None,
    pass_score: int,
    questions: list[QuestionIn],
) -> TestDetail:
    test = Test(
        venue_id=venue_id,
        title=title,
        description=description,
        source=source,
        source_detail=source_detail,
        created_by_employee_id=created_by_employee_id,
        deadline=deadline,
        pass_score=pass_score,
    )
    session.add(test)
    await session.flush()  # нужен test.id для test_questions

    for position, q in enumerate(questions):
        session.add(
            TestQuestion(
                test_id=test.id,
                position=position,
                question=q.question,
                options=q.options,
                correct_index=q.correct_index,
                explain=q.explain,
                source=q.source,
            )
        )
    await session.flush()
    return await get_owned_test(session, venue_id, test.id)


async def get_owned_test(session: AsyncSession, venue_id: int, test_id: int) -> TestDetail:
    test = await session.get(Test, test_id)
    if test is None or test.venue_id != venue_id:
        raise TestNotFoundError(test_id)
    return await _fetch_detail(session, venue_id, test)


async def list_tests(session: AsyncSession, venue_id: int) -> list[TestDetail]:
    """Все тесты точки — кабинет руководителя (с вопросами/назначениями/результатами)."""
    tests = (
        (
            await session.execute(
                select(Test).where(Test.venue_id == venue_id).order_by(Test.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [await _fetch_detail(session, venue_id, test) for test in tests]


async def list_assigned_tests(
    session: AsyncSession, venue_id: int, employee_id: int
) -> list[TestDetail]:
    """Тесты, назначенные сотруднику — кабинет сотрудника.

    Отдаёт TestDetail как есть (включая correct_index/explain) — не подсказывать
    ответы до прохождения обязан слой маппинга в app/api/training.py
    (TestForEmployeeOut), а не этот сервис.
    """
    tests = (
        (
            await session.execute(
                select(Test)
                .join(TestAssignment, TestAssignment.test_id == Test.id)
                .where(Test.venue_id == venue_id, TestAssignment.employee_id == employee_id)
                .order_by(Test.deadline.is_(None), Test.deadline)
            )
        )
        .scalars()
        .all()
    )
    return [await _fetch_detail(session, venue_id, test) for test in tests]


async def assign_test(
    session: AsyncSession,
    venue_id: int,
    test_id: int,
    *,
    employee_ids: list[int],
    assigned_by_employee_id: int,
) -> TestDetail:
    """Назначить тест списку сотрудников. Идемпотентно: уже назначенным — no-op,
    не ошибка (руководитель мог довызвать список, не помня, кому уже назначал)."""
    detail = await get_owned_test(session, venue_id, test_id)
    already_assigned = set(detail.assigned_employee_ids)
    for employee_id in employee_ids:
        if employee_id in already_assigned:
            continue
        await _get_owned_employee(session, venue_id, employee_id)
        session.add(
            TestAssignment(
                test_id=test_id,
                employee_id=employee_id,
                assigned_by_employee_id=assigned_by_employee_id,
            )
        )
    await session.flush()
    return await get_owned_test(session, venue_id, test_id)


async def submit_test(
    session: AsyncSession,
    venue_id: int,
    test_id: int,
    employee_id: int,
    *,
    answers: list[int],
) -> TestResult:
    """Сохранить результат прохождения. NotAssignedError — тест не назначался
    этому сотруднику; AlreadyCompletedError — уже проходил."""
    detail = await get_owned_test(session, venue_id, test_id)
    if employee_id not in detail.assigned_employee_ids:
        raise NotAssignedError(test_id, employee_id)
    if any(r.employee_id == employee_id for r in detail.results):
        raise AlreadyCompletedError(test_id, employee_id)

    correct_indices = [q.correct_index for q in detail.questions]
    score_percent = score_test(answers, correct_indices)

    result = TestResult(
        test_id=test_id,
        employee_id=employee_id,
        score_percent=score_percent,
        answers=answers,
    )
    session.add(result)
    await session.flush()
    await session.refresh(result)
    return result


async def list_results(session: AsyncSession, venue_id: int, test_id: int) -> list[TestResult]:
    detail = await get_owned_test(session, venue_id, test_id)
    return sorted(detail.results, key=lambda r: r.completed_at, reverse=True)
