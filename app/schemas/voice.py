from pydantic import BaseModel

from app.schemas.product import ProductOut


class VoiceAssistantResult(BaseModel):
    """Результат голосового запроса к ассистенту.

    query_text — что распознали; answer_text — что ответили; audio_base64 —
    озвученный ответ (MP3, base64) для проигрывания в наушники.

    intent маршрутизирует поведение клиента:
    - "answer"  — ассистент ответил по каталогу (обычный режим);
    - "connect" — просьба соединить по рации; клиент подставляет получателя;
    - "ignored" — режим постоянного прослушивания: «Онви» не прозвучало,
      фраза не обработана (без очков, лога и озвучки).
    """

    query_text: str
    answer_text: str
    found: bool
    matched: list[ProductOut]
    audio_base64: str = ""
    # Активация и маршрутизация
    wake_word: bool = False
    intent: str = "answer"
    connect_target_id: int | None = None
    connect_target_name: str | None = None
    connect_whole_department: bool = False


class VoiceCommsResult(BaseModel):
    """Результат отправки голосовой реплики по связи."""

    message_id: int
    recognized_text: str
    source_language: str
    delivered_to: list[int]  # кому реально доставили (был онлайн)
