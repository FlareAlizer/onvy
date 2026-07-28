from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DialogueAnalysis(Base):
    """Разбор одного диалога с покупателем (результат конвейера аналитики).

    recording_id группирует диалоги, нарезанные из одной записи.
    """

    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id"), nullable=True, index=True
    )
    recording_id: Mapped[str] = mapped_column(default="", index=True)
    transcript: Mapped[str] = mapped_column(Text)
    analysis_json: Mapped[str] = mapped_column(Text)  # полный разбор (JSON от LLM)
    kpi_score: Mapped[int] = mapped_column(default=0)
    is_sold: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
