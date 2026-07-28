from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import SoftDeleteMixin, TimestampMixin


class CommGroup(TimestampMixin, SoftDeleteMixin, Base):
    """Группа связи точки: зал / кухня / бар / все.

    Маршрутизация голосом ("Онви, скажи кухне...") резолвит имя группы в
    comm_group.id и рассылает всем активным участникам (S3, S5).
    """

    __tablename__ = "comm_groups"
    __table_args__ = (
        # Имя группы уникально в рамках точки, но допускает переиспользование
        # имени после мягкого удаления старой группы (partial unique index).
        Index(
            "ux_comm_groups_venue_name_active",
            "venue_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(60))


class EmployeeCommGroup(Base):
    """Членство сотрудника в группе связи (many-to-many employee <-> comm_group)."""

    __tablename__ = "employee_comm_groups"

    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True
    )
    comm_group_id: Mapped[int] = mapped_column(
        ForeignKey("comm_groups.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
