from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import KPI_METRICS, KPI_PERIODS, sql_in
from app.db.models.mixins import TimestampMixin


class Kpi(TimestampMixin, Base):
    """Цель, которую управляющий поставил сотруднику (фронт: интерфейс `Kpi`).

    `metric` ограничен KPI_METRICS — только то, что реально можно посчитать из
    наших данных (assistant_queries/utterances), см. app/services/stats.py.
    Выручку, средний чек и конверсию сюда осознанно не пускаем: без POS-
    интеграции "текущее значение" по ним нечем посчитать честно.

    `period_start`/`period_end` — границы окна, за которое считается `current`
    (день/неделя/месяц). Храним обе даты явно, а не только период: иначе после
    конца периода невозможно понять, какое именно окно имелась в виду цель.

    Одна активная цель на (сотрудник, метрика, период, period_start) —
    повторная постановка в services/kpi.py обновляет target/note той же строки,
    а не плодит дубликаты (та же идиома, что stop_list_entries.set_stop).
    """

    __tablename__ = "kpis"
    __table_args__ = (
        CheckConstraint(sql_in("metric", KPI_METRICS), name="metric_valid"),
        CheckConstraint(sql_in("period", KPI_PERIODS), name="period_valid"),
        Index(
            "ux_kpis_employee_metric_period_start",
            "employee_id",
            "metric",
            "period",
            "period_start",
            unique=True,
        ),
        Index("ix_kpis_venue_period_start", "venue_id", "period_start"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id", ondelete="RESTRICT"), index=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), index=True
    )
    metric: Mapped[str] = mapped_column(String(40))
    target: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    period: Mapped[str] = mapped_column(String(10))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    set_by_employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
