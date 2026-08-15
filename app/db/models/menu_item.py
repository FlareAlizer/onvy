from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import SoftDeleteMixin, TimestampMixin


class MenuItem(TimestampMixin, SoftDeleteMixin, Base):
    """Позиция меню точки — источник правды для ассистента (S1, S2).

    Техкарта (состав/аллергены/острота/вес/время отдачи) ВСЕГДА опциональна:
    заведения массово не ведут техкарты (spec §8, §9). NULL значит "данных
    нет" — ассистент обязан честно ответить "по этому блюду данных нет"
    (S2, юридически значимо для аллергенов — требование ЗоЗПП к заведению,
    угадывать запрещено). Пустое значение — это подтверждённый факт от
    кухни ("аллергенов нет"), а не пропуск заполнения; поэтому NULL и
    "пусто" осознанно различаются на уровне колонки, а не только в UI:
      - allergens = NULL       -> не проверялись, ассистент должен уточнить
      - allergens = '{}'       -> кухня подтвердила: аллергенов нет

    Наличие/отсутствие позиции "сейчас" — не колонка здесь, а отдельный
    живой поток `stop_list_entries` (см. этот файл рядом) с историей;
    is_active/деактивация в этой таблице означает окончательное снятие
    блюда с меню (soft-delete), а не "закончилось на сегодня".
    """

    __tablename__ = "menu_items"
    __table_args__ = (
        CheckConstraint(
            "spiciness IS NULL OR spiciness BETWEEN 0 AND 3", name="spiciness_range"
        ),
        CheckConstraint("price >= 0", name="price_non_negative"),
        # Позицию опознаём по названию ВМЕСТЕ с разделом. В реальных меню одно
        # название живёт в нескольких разделах с разной ценой и выходом («Чай
        # облепиховый» в чайниках и порционно, «Салат Цезарь» с курицей и с
        # креветками в разных группах). Уникальность по одному названию
        # отклоняла такие строки при загрузке файла — заведение теряло позиции.
        Index(
            "ux_menu_items_venue_name_category_active",
            "venue_id",
            "name",
            "category",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_menu_items_venue_category", "venue_id", "category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(120), default="")
    # Цена в минимальной валютной единице (без float — не копим ошибку округления).
    price: Mapped[int] = mapped_column(Integer, default=0)

    # --- Техкарта: всё ниже NULLABLE. NULL = "не заполнено", не "пусто". ---
    composition: Mapped[str | None] = mapped_column(Text, nullable=True)
    # NULL = аллергены не проверялись; [] (пустой массив) = кухня подтвердила
    # явно: аллергенов нет.
    allergens: Mapped[list[str] | None] = mapped_column(ARRAY(String(60)), nullable=True)
    # 0..3 (не острое..очень острое), NULL = не указано.
    spiciness: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    portion_weight_g: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prep_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
