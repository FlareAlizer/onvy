from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """created_at/updated_at в timestamptz — обязательны для бизнес-сущностей."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SoftDeleteMixin:
    """Мягкое удаление: deleted_at IS NULL значит "запись активна".

    Бизнес-сущности (venue, employee, comm_group, menu_item) не удаляются
    физически — на них могут ссылаться реплики/запросы/стоп-лист, нужные
    для аналитики пилота задним числом (см. FK ondelete=RESTRICT рядом).
    """

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
