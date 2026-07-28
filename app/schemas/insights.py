"""Схемы данных смены и метрик пилота."""

from datetime import datetime

from pydantic import BaseModel, Field


class PresenceOut(BaseModel):
    """Кто на смене прямо сейчас."""

    online_employee_ids: list[int] = Field(default_factory=list)
    online_names: list[str] = Field(default_factory=list)


class UtteranceOut(BaseModel):
    """Реплика рации в ленте управляющего."""

    id: int
    sender_id: int
    source_language: str
    source_text: str
    translated_text: str | None
    target_language: str
    translation_failed: bool
    total_ms: int | None
    created_at: datetime


class AssistantQueryOut(BaseModel):
    """Вопрос к ассистенту и что он ответил."""

    id: int
    employee_id: int
    query_text: str
    answer_text: str
    menu_item_found: bool
    total_ms: int | None
    created_at: datetime


class MetricsSummary(BaseModel):
    """Сводка за период.

    Латентность — медиана и 95-й процентиль, без среднего: один зависший запрос
    перекашивает среднее целиком, а важно, как часто официант ждёт дольше
    терпимого. Пустое значение честнее нуля — значит, данных пока нет.
    """

    days: int
    assistant_queries: int
    assistant_answered: int
    assistant_missed: int
    median_ms: int | None
    p95_ms: int | None
    utterances: int
    translated: int
    translation_failures: int
