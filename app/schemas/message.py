from datetime import datetime

from pydantic import BaseModel, Field


class MessageIn(BaseModel):
    """Отправка реплики по связи."""

    sender_id: int
    recipient_id: int | None = Field(default=None, description="None = broadcast всем на смене")
    text: str = Field(min_length=1)


class MessageOut(BaseModel):
    """Сохранённая реплика (оригинал на языке отправителя)."""

    id: int
    sender_id: int
    recipient_id: int | None
    text: str
    source_language: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DeliveredMessage(BaseModel):
    """Реплика, доставленная конкретному получателю — с переводом под его язык."""

    id: int
    sender_id: int
    recipient_id: int | None
    original_text: str
    source_language: str
    text: str  # текст на языке получателя (или оригинал, если перевод не нужен)
    target_language: str
    translated: bool  # был ли применён реальный движок перевода
    translation_provider: str
    created_at: datetime
