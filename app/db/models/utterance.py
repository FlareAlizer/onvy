from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import LANGUAGES, sql_in


class Utterance(Base):
    """Реплика рации: оригинал + перевод + метрики стадий (S3).

    Ровно один из recipient_employee_id / recipient_group_id заполнен —
    личное сообщение или групповой broadcast, не оба и не ни одного
    (ck_utterances_single_recipient_kind).

    Оригинал хранится всегда. Перевод хранится, если он удался; при отказе
    перевода translation_failed=true и получателю доставляется оригинал
    с явной пометкой — "никогда не тишина" (S3, приёмка).
    """

    __tablename__ = "utterances"
    __table_args__ = (
        CheckConstraint(
            "(recipient_employee_id IS NOT NULL)::int "
            "+ (recipient_group_id IS NOT NULL)::int = 1",
            name="single_recipient_kind",
        ),
        CheckConstraint(sql_in("source_language", LANGUAGES), name="source_language_valid"),
        CheckConstraint(sql_in("target_language", LANGUAGES), name="target_language_valid"),
        # Лента реплик по точке и времени — основной экран управляющего (S6).
        Index("ix_utterances_venue_created", "venue_id", "created_at"),
        # Личная история сотрудника (переписка/реплики за смену).
        Index("ix_utterances_sender_created", "sender_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id", ondelete="RESTRICT"))
    sender_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"))
    recipient_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), nullable=True
    )
    recipient_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("comm_groups.id", ondelete="RESTRICT"), nullable=True
    )

    source_language: Mapped[str] = mapped_column(String(8))
    source_text: Mapped[str] = mapped_column(Text)
    target_language: Mapped[str] = mapped_column(String(8))
    translated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    translation_failed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Метрики стадий, мс. NULLABLE — деградация (§6) может пропустить стадию
    # (например TTS при падении речевого стека), метрика тогда неизвестна,
    # а не "0 мс".
    asr_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    translate_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tts_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
