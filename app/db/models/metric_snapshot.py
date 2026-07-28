from datetime import date

from sqlalchemy import Date, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin


class MetricSnapshot(TimestampMixin, Base):
    """Дневной срез метрик пилота — для выгрузки CSV (S6, specs §10).

    Состав метрик (средний чек, латентность по стадиям p95, число реплик,
    доля неудачных переводов и т.д.) будет уточняться по ходу пилота
    (30-31 июля) — JSONB вместо жёстких колонок, чтобы новая метрика не
    требовала блокирующей миграции в разгар пилота. unique(venue_id,
    snapshot_date) — снимок на день один, повторный расчёт делает upsert,
    а не плодит дубликаты строк.
    """

    __tablename__ = "metric_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "venue_id", "snapshot_date", name="uq_metric_snapshots_venue_snapshot_date"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id", ondelete="RESTRICT"), index=True)
    snapshot_date: Mapped[date] = mapped_column(Date)
    metrics: Mapped[dict] = mapped_column(JSONB)
