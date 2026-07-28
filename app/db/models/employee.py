from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import EMPLOYEE_ROLES, LANGUAGES, sql_in
from app.db.models.mixins import SoftDeleteMixin, TimestampMixin


class Employee(TimestampMixin, SoftDeleteMixin, Base):
    """Сотрудник точки — держатель гарнитуры/PWA Onvy.

    Идентификация — PIN (пилот), затем PIN + JWT с ролями (spec §5/§8).
    Правовое ограничение (specs/pilot-chaihana.md §2): продукт НЕ
    идентифицирует человека по голосу. pin_hash — единственный секрет
    сотрудника; голос обрабатывается только как носитель смысла, никакого
    voice-ID/биометрического слепка в этой или любой другой таблице нет.

    pin_hash — argon2id, соленый: по нему нельзя сделать обратный lookup
    "по PIN найти сотрудника". Экран логина показывает список сотрудников
    точки по имени, сотрудник выбирает себя и вводит PIN на проверку —
    это ответственность auth-сервиса, не этой таблицы.
    """

    __tablename__ = "employees"
    __table_args__ = (
        CheckConstraint(sql_in("role", EMPLOYEE_ROLES), name="role_valid"),
        CheckConstraint(sql_in("language", LANGUAGES), name="language_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))
    # Язык сотрудника: на нём он говорит и слышит перевод/TTS-подсказки.
    language: Mapped[str] = mapped_column(String(8), default="ru")
    pin_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    hired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
