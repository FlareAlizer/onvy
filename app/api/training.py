"""REST тестов обучения (задание лупа, п.5): создать тест, назначить
сотрудникам, пройти, сохранить результат. Генерация вопросов ИИ — не здесь,
вопросы приходят готовыми в теле создания.

Права: создание/список всех тестов/назначение/результаты — только
управляющий; список своих назначенных тестов и отправка ответов — любой
аутентифицированный сотрудник, только за себя.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.menu import require_own_venue
from app.db import get_session
from app.deps import CurrentEmployee, require_employee, require_manager
from app.schemas.training import (
    TestAssignIn,
    TestCreateIn,
    TestForEmployeeOut,
    TestOut,
    TestQuestionForEmployeeOut,
    TestQuestionOut,
    TestQuestionReviewOut,
    TestResultOut,
    TestResultSummaryOut,
    TestSubmitIn,
)
from app.services import training as training_service

router = APIRouter(prefix="/venues/{venue_id}", tags=["training"])


def _map_test(detail: training_service.TestDetail) -> TestOut:
    test = detail.test
    return TestOut(
        id=test.id,
        title=test.title,
        description=test.description,
        source=test.source,
        source_detail=test.source_detail,
        created_at=test.created_at,
        created_by_employee_id=test.created_by_employee_id,
        deadline=test.deadline,
        pass_score=test.pass_score,
        questions=[
            TestQuestionOut(
                id=q.id,
                position=q.position,
                question=q.question,
                options=q.options,
                correct_index=q.correct_index,
                explain=q.explain,
                source=q.source,
            )
            for q in detail.questions
        ],
        assigned_employee_ids=detail.assigned_employee_ids,
        results=[
            TestResultSummaryOut(
                employee_id=r.employee_id,
                score_percent=r.score_percent,
                passed=r.score_percent >= test.pass_score,
                completed_at=r.completed_at,
            )
            for r in detail.results
        ],
    )


def _map_test_for_employee(
    detail: training_service.TestDetail, employee_id: int
) -> TestForEmployeeOut:
    """Вопросы без correct_index/explain — сотрудник не должен видеть ответ до
    прохождения (см. app/schemas/training.py TestQuestionForEmployeeOut)."""
    test = detail.test
    own_result = next((r for r in detail.results if r.employee_id == employee_id), None)
    return TestForEmployeeOut(
        id=test.id,
        title=test.title,
        description=test.description,
        deadline=test.deadline,
        pass_score=test.pass_score,
        questions=[
            TestQuestionForEmployeeOut(
                id=q.id, position=q.position, question=q.question, options=q.options
            )
            for q in detail.questions
        ],
        completed=own_result is not None,
        score_percent=own_result.score_percent if own_result else None,
    )


@router.post("/tests", response_model=TestOut, status_code=status.HTTP_201_CREATED)
async def create_test(
    venue_id: int,
    payload: TestCreateIn,
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> TestOut:
    require_own_venue(current, venue_id)
    detail = await training_service.create_test(
        db,
        venue_id,
        title=payload.title,
        description=payload.description,
        source=payload.source,
        source_detail=payload.source_detail,
        created_by_employee_id=current.id,
        deadline=payload.deadline,
        pass_score=payload.pass_score,
        questions=[
            training_service.QuestionIn(
                question=q.question,
                options=q.options,
                correct_index=q.correct_index,
                explain=q.explain,
                source=q.source,
            )
            for q in payload.questions
        ],
    )
    await db.commit()
    return _map_test(detail)


@router.get("/tests", response_model=list[TestOut])
async def list_tests(
    venue_id: int,
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> list[TestOut]:
    """Все тесты точки — кабинет руководителя."""
    require_own_venue(current, venue_id)
    details = await training_service.list_tests(db, venue_id)
    return [_map_test(d) for d in details]


@router.get("/tests/mine", response_model=list[TestForEmployeeOut])
async def list_my_tests(
    venue_id: int,
    current: CurrentEmployee = Depends(require_employee),
    db: AsyncSession = Depends(get_session),
) -> list[TestForEmployeeOut]:
    """Тесты, назначенные мне — кабинет сотрудника."""
    require_own_venue(current, venue_id)
    details = await training_service.list_assigned_tests(db, venue_id, current.id)
    return [_map_test_for_employee(d, current.id) for d in details]


@router.post("/tests/{test_id}/assign", response_model=TestOut)
async def assign_test(
    venue_id: int,
    test_id: int,
    payload: TestAssignIn,
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> TestOut:
    require_own_venue(current, venue_id)
    try:
        detail = await training_service.assign_test(
            db,
            venue_id,
            test_id,
            employee_ids=payload.employee_ids,
            assigned_by_employee_id=current.id,
        )
    except training_service.TestNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except training_service.EmployeeNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await db.commit()
    return _map_test(detail)


@router.post("/tests/{test_id}/submit", response_model=TestResultOut)
async def submit_test(
    venue_id: int,
    test_id: int,
    payload: TestSubmitIn,
    current: CurrentEmployee = Depends(require_employee),
    db: AsyncSession = Depends(get_session),
) -> TestResultOut:
    """Отправить ответы. Разбор (какой ответ был правильным) отдаётся сразу
    же в ответе — это единственный момент, когда сотрудник видит correct_index."""
    require_own_venue(current, venue_id)
    try:
        detail_before = await training_service.get_owned_test(db, venue_id, test_id)
    except training_service.TestNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    try:
        result = await training_service.submit_test(
            db, venue_id, test_id, current.id, answers=payload.answers
        )
    except training_service.NotAssignedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except training_service.AlreadyCompletedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    await db.commit()

    ordered_questions = sorted(detail_before.questions, key=lambda q: q.position)
    review = [
        TestQuestionReviewOut(
            id=q.id,
            position=q.position,
            question=q.question,
            options=q.options,
            correct_index=q.correct_index,
            given_index=given,
            is_correct=given == q.correct_index,
            explain=q.explain,
        )
        for q, given in zip(ordered_questions, payload.answers, strict=True)
    ]
    return TestResultOut(
        test_id=test_id,
        employee_id=current.id,
        score_percent=result.score_percent,
        passed=result.score_percent >= detail_before.test.pass_score,
        completed_at=result.completed_at,
        review=review,
    )


@router.get("/tests/{test_id}/results", response_model=list[TestResultSummaryOut])
async def test_results(
    venue_id: int,
    test_id: int,
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> list[TestResultSummaryOut]:
    require_own_venue(current, venue_id)
    try:
        detail = await training_service.get_owned_test(db, venue_id, test_id)
    except training_service.TestNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    results = await training_service.list_results(db, venue_id, test_id)
    return [
        TestResultSummaryOut(
            employee_id=r.employee_id,
            score_percent=r.score_percent,
            passed=r.score_percent >= detail.test.pass_score,
            completed_at=r.completed_at,
        )
        for r in results
    ]
