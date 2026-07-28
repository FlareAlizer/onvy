from pydantic import BaseModel, Field

from app.schemas.product import ProductOut


class AssistantQuery(BaseModel):
    """Запрос сотрудника к ассистенту.

    Текст приходит уже распознанным: ASR (GigaAM/SpeechKit) работает на
    устройстве/в приложении, бэкенд получает текст.
    """

    text: str = Field(min_length=1, description="Распознанный текст запроса")
    employee_id: int | None = Field(
        default=None, description="Кто спрашивает (для языка ответа и логов)"
    )


class AssistantAnswer(BaseModel):
    """Ответ ассистента — «подсказка в ухо».

    Поле answer — готовый текст для синтеза речи (TTS) на устройстве.
    """

    answer: str
    matched: list[ProductOut]
    found: bool
