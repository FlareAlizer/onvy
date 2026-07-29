from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import EMPLOYEE_ROLES, LANGUAGES, sql_in
from app.db.models.mixins import SoftDeleteMixin, TimestampMixin


class Employee(TimestampMixin, SoftDeleteMixin, Base):
    """Сотрудник точки — держатель гарнитуры/PWA Onvy.

    Вход двумя способами: по почте с паролем (основной) и по PIN из списка
    смены (быстрый, для линейного персонала в зале). Оба ведут к одной и той же
    паре JWT — дальше система не различает, как человек вошёл.
    Правовое ограничение (specs/pilot-chaihana.md §2): продукт НЕ
    идентифицирует человека по голосу. pin_hash — единственный секрет
    сотрудника; голос обрабатывается только как носитель смысла, никакого
    voice-ID/биометрического слепка в этой или любой другой таблице нет.

    pin_hash и password_hash — argon2id, солёные: обратного поиска по ним нет.
    Экран входа по PIN показывает список сотрудников точки по имени, человек
    выбирает себя и вводит PIN — проверка на стороне auth-сервиса, не здесь.
    """

    __tablename__ = "employees"
    __table_args__ = (
        CheckConstraint(sql_in("role", EMPLOYEE_ROLES), name="role_valid"),
        CheckConstraint(sql_in("language", LANGUAGES), name="language_valid"),
        # Кличка уникальна в точке: двух «Азизов» на смене голосовая адресация
        # развести не сможет. Индекс частичный — уволенные освобождают кличку,
        # а сотрудники без клички индекс не занимают.
        Index(
            "ux_employees_venue_nickname_active",
            "venue_id",
            "nickname",
            unique=True,
            postgresql_where=text("nickname IS NOT NULL AND deleted_at IS NULL"),
        ),
        # Почта уникальна глобально, а не в пределах точки: по ней входят, и
        # один адрес не может вести к двум разным людям в разных заведениях.
        # Индекс частичный — уволенные освобождают адрес, сотрудники без почты
        # (вход только по PIN) индекс не занимают.
        Index(
            "ux_employees_email_active",
            "email",
            unique=True,
            postgresql_where=text("email IS NOT NULL AND deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    # Короткая кличка на смене ("Азиз" при полном имени "Азизбек Рахматуллаев") —
    # голосовая маршрутизация (app/domain/intents.py, Colleague) ищет обращение
    # по ней в первую очередь: распознавание в шуме справляется с кличкой
    # заметно лучше, чем с длинным полным именем. NULL — клички нет, обращение
    # ищут по первому слову name (см. Colleague.spoken_forms).
    nickname: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # Почта и пароль — основной способ входа. Оба nullable: линейному персоналу
    # почту заводить необязательно, им хватает быстрого входа по PIN, и это не
    # прихоть — официант вводит его одной рукой, не глядя, с подносом в другой.
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(20))
    # Язык сотрудника: на нём он говорит и слышит перевод/TTS-подсказки.
    language: Mapped[str] = mapped_column(String(8), default="ru")
    pin_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    hired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
