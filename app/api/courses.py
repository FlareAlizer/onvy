"""Обучение: генерация курсов YandexGPT, список, прогресс сотрудника."""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.deps import require_api_key
from app.models.course import Course, CourseProgress
from app.schemas.course import CourseOut, GenerateCourseIn, ProgressIn
from app.services import courses as course_service
from app.services import gamification
from app.services.llm import LLMError

router = APIRouter(tags=["courses"], dependencies=[Depends(require_api_key)])

# Очки геймификации за пройденный курс.
POINTS_COURSE_DONE = 25


def _to_out(course: Course, progress: int = 0) -> CourseOut:
    return CourseOut(
        id=course.id,
        title=course.title,
        description=course.description,
        category=course.category,
        steps=json.loads(course.steps_json),
        progress=progress,
    )


@router.post("/courses/generate", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
async def generate_course(
    payload: GenerateCourseIn, db: AsyncSession = Depends(get_session)
) -> CourseOut:
    """Сгенерировать курс по теме (и опциональному материалу) и сохранить."""
    if not settings.yandex_enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Yandex не настроен (YANDEX_API_KEY/YANDEX_FOLDER_ID)",
        )
    try:
        data = await course_service.generate_course(payload.topic, payload.material)
    except LLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="Ошибка генерации курса") from exc

    course = Course(
        title=str(data.get("title", payload.topic))[:200],
        description=str(data.get("description", "")),
        category=str(data.get("category", "Sales"))[:60],
        steps_json=json.dumps(data.get("steps", []), ensure_ascii=False),
    )
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return _to_out(course)


@router.get("/courses", response_model=list[CourseOut])
async def list_courses(
    employee_id: int | None = None, db: AsyncSession = Depends(get_session)
) -> list[CourseOut]:
    """Все курсы; с employee_id — с прогрессом этого сотрудника."""
    courses = (await db.execute(select(Course))).scalars().all()
    progress_map: dict[int, int] = {}
    if employee_id is not None:
        rows = (
            (
                await db.execute(
                    select(CourseProgress).where(CourseProgress.employee_id == employee_id)
                )
            )
            .scalars()
            .all()
        )
        progress_map = {r.course_id: r.progress for r in rows}
    return [_to_out(c, progress_map.get(c.id, 0)) for c in courses]


@router.post("/courses/progress", response_model=CourseOut)
async def update_progress(
    payload: ProgressIn, db: AsyncSession = Depends(get_session)
) -> CourseOut:
    """Сохранить прогресс; за первое прохождение на 100% — очки геймификации."""
    course = await db.get(Course, payload.course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Курс не найден")

    row = (
        (
            await db.execute(
                select(CourseProgress).where(
                    CourseProgress.employee_id == payload.employee_id,
                    CourseProgress.course_id == payload.course_id,
                )
            )
        )
        .scalars()
        .first()
    )

    was_done = row is not None and row.progress >= 100
    if row is None:
        row = CourseProgress(
            employee_id=payload.employee_id,
            course_id=payload.course_id,
            progress=payload.progress,
        )
        db.add(row)
    else:
        row.progress = max(row.progress, payload.progress)  # прогресс не откатываем

    if not was_done and payload.progress >= 100:
        await gamification.award_points(db, payload.employee_id, POINTS_COURSE_DONE)

    await db.commit()
    return _to_out(course, row.progress)
