from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StopListEntry(Base):
    """Запись стоп-листа: "блюда нет сейчас" (S4).

    Живой поток, а не флаг на menu_item (spec §8, §9): каждое включение и
    каждое снятие позиции — отдельная строка. unset_at IS NULL значит
    "сейчас в стопе". Полная история нужна для аналитики пилота — сколько
    раз и как долго позиция была недоступна за смену/день.
    """

    __tablename__ = "stop_list_entries"
    __table_args__ = (
        # S4, приёмка: "следующий запрос уже знает" — активный стоп-лист
        # точки проверяется на каждый вопрос ассистента про блюдо, это
        # самый горячий путь на этой таблице.
        Index(
            "ix_stop_list_entries_active",
            "venue_id",
            "menu_item_id",
            postgresql_where=text("unset_at IS NULL"),
        ),
        # История/аналитика: сколько раз и когда точка держала позиции в стопе.
        Index("ix_stop_list_entries_venue_set_at", "venue_id", "set_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id", ondelete="RESTRICT"))
    menu_item_id: Mapped[int] = mapped_column(
        ForeignKey("menu_items.id", ondelete="CASCADE"), index=True
    )
    set_by_employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"))
    unset_by_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    set_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    unset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
