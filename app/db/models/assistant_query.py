from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AssistantQuery(Base):
    """Запрос к голосовому ассистенту над меню (S1, S2) + метрики стадий.

    Какие позиции меню подтянулись в ответ — не ARRAY(Integer), а отдельная
    таблица-связка `assistant_query_menu_items` (ниже): у ссылки должна быть
    настоящая FK-целостность, а не список чисел без гарантий.
    """

    __tablename__ = "assistant_queries"
    __table_args__ = (
        # "запросы сотрудника за смену" — индекс явно из specs/pilot-chaihana.md §9.
        Index("ix_assistant_queries_employee_created", "employee_id", "created_at"),
        Index("ix_assistant_queries_venue_created", "venue_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id", ondelete="RESTRICT"))
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"))

    query_text: Mapped[str] = mapped_column(Text)
    answer_text: Mapped[str] = mapped_column(Text)
    # Ответ строится только по данным меню (S1, приёмка) — этот флаг
    # фиксирует, что поиск вообще что-то нашёл, а не что модель досочинила.
    menu_item_found: Mapped[bool] = mapped_column(Boolean, default=False)

    # Три стадии латентности из §6 (запись меряется отдельно на клиенте):
    # ASR -> поиск/LLM -> TTS. llm_ms (а не translate_ms, как у Utterance) —
    # ответ строится сразу на языке сотрудника, отдельного шага перевода
    # в этом сценарии нет.
    asr_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tts_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AssistantQueryMenuItem(Base):
    """Связка: какие позиции меню подтянулись в ответ ассистента."""

    __tablename__ = "assistant_query_menu_items"

    assistant_query_id: Mapped[int] = mapped_column(
        ForeignKey("assistant_queries.id", ondelete="CASCADE"), primary_key=True
    )
    menu_item_id: Mapped[int] = mapped_column(
        ForeignKey("menu_items.id", ondelete="RESTRICT"), primary_key=True, index=True
    )
