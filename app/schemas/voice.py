"""Схемы голосового API.

Ответ намеренно самоописательный: клиент в зале должен понимать не только что
сказать в ухо, но и что именно отвалилось, если отвалилось. Тихая деградация,
неотличимая от нормального ответа, — худшее, что можно сделать с официантом,
стоящим перед гостем.
"""

from pydantic import BaseModel, Field


class StageMetricsOut(BaseModel):
    """Сколько заняла каждая стадия. Основа отчёта по латентности пилота."""

    asr_ms: int = 0
    search_ms: int = 0
    answer_ms: int = 0
    tts_ms: int = 0
    total_ms: int = 0


class VoiceResult(BaseModel):
    """Результат нажатия кнопки."""

    intent: str = Field(description="ask, send_group, send_person, empty или ignored")
    query_text: str = Field(default="", description="Что распознали")
    answer_text: str = Field(default="", description="Что сказать сотруднику в ухо")
    audio_base64: str | None = Field(
        default=None, description="Озвученный ответ; пусто, если синтез отказал"
    )
    mime_type: str = "audio/mpeg"
    grounded_on: list[str] = Field(
        default_factory=list, description="Позиции меню, на которых основан ответ"
    )
    degraded: str | None = Field(
        default=None, description="Что отказало: asr, answer или tts"
    )
    # Заполняется, когда реплика ушла в рацию.
    delivered_to: list[int] = Field(default_factory=list)
    group: str | None = None
    person_name: str | None = None
    metrics: StageMetricsOut = Field(default_factory=StageMetricsOut)


class TextMessageIn(BaseModel):
    """Текстовая реплика — запасной путь, когда говорить нельзя или слишком шумно."""

    text: str = Field(min_length=1, max_length=1000)
    group: str | None = Field(default=None, description="зал, кухня, бар или все")
    recipient_id: int | None = None


class TextMessageResult(BaseModel):
    delivered_to: list[int] = Field(default_factory=list)
    translation_failed: bool = False


class AssistantAskIn(BaseModel):
    """Вопрос ассистенту текстом — когда в зале шумно или говорить при госте неловко."""

    text: str = Field(min_length=1, max_length=500)
    speak: bool = Field(
        default=True, description="Озвучивать ответ. Выключается, когда нужен только текст"
    )
