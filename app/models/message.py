from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Message(Base):
    """Реплика связи между сотрудниками (рация + перевод).

    recipient_id = NULL означает broadcast (всем на смене).
    Хранится оригинальный текст на языке отправителя; перевод под язык
    получателя считается на лету сервисом перевода.
    """

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    recipient_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    source_language: Mapped[str] = mapped_column(default="ru")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
