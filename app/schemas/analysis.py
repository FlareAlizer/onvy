from datetime import datetime

from pydantic import BaseModel, Field


class AnalyzeTextIn(BaseModel):
    """Транскрибация на разбор (без аудио — например, для проверки текстом)."""

    text: str = Field(min_length=1)
    employee_id: int | None = None


class AnalysisSummary(BaseModel):
    """Строка в списке разборов."""

    id: int
    employee_id: int | None
    recording_id: str
    kpi_score: int
    is_sold: bool
    summary: str
    created_at: datetime


class AnalysisDetail(BaseModel):
    """Полный разбор диалога."""

    id: int
    employee_id: int | None
    recording_id: str
    transcript: str
    kpi_score: int
    is_sold: bool
    analysis: dict
    created_at: datetime


class UploadResult(BaseModel):
    """Итог обработки записи: транскрибация + разборы всех найденных диалогов."""

    recording_id: str
    transcript: str
    dialogues_found: int
    analyses: list[AnalysisDetail]
