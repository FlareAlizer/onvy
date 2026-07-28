from sqlalchemy import Boolean, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import LANGUAGES, sql_in
from app.db.models.mixins import SoftDeleteMixin, TimestampMixin


class Venue(TimestampMixin, SoftDeleteMixin, Base):
    """Точка (заведение) — единица мультитенантности.

    Пилот — одна чайхана, но venue_id закладывается во все доменные таблицы
    с первого дня (specs/pilot-chaihana.md §9): масштабирование на вторую и
    десятую точку — это новая строка здесь, а не миграция схемы.
    """

    __tablename__ = "venues"
    __table_args__ = (
        # Имя без префикса "ck_<table>_" — его достраивает naming_convention
        # из app/db/base.py (для CheckConstraint явное имя всё равно проходит
        # через шаблон %(constraint_name)s, поэтому префикс не дублируем).
        CheckConstraint(sql_in("default_language", LANGUAGES), name="default_language_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    # IANA timezone (напр. "Asia/Yekaterinburg") — локальное время смен и метрик.
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")
    # Язык по умолчанию для UI/подсказок, если у сотрудника язык не задан явно.
    default_language: Mapped[str] = mapped_column(String(8), default="ru")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
