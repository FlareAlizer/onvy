from pydantic import BaseModel, Field


class GenerateCourseIn(BaseModel):
    """Запрос на генерацию курса."""

    topic: str = Field(min_length=1, max_length=300)
    material: str = Field(default="", description="Опциональный материал/ошибки для курса")


class CourseOut(BaseModel):
    """Курс с шагами."""

    id: int
    title: str
    description: str
    category: str
    steps: list[dict]
    progress: int = 0  # прогресс запрашивающего сотрудника (если передан)


class ProgressIn(BaseModel):
    """Обновление прогресса прохождения."""

    employee_id: int
    course_id: int
    progress: int = Field(ge=0, le=100)
