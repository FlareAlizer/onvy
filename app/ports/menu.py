"""Порт источника меню и стоп-листа.

Меню на пилоте вводится руками и импортом CSV, потом появится адаптер iiko/R-Keeper.
Контракт спроектирован под реальность учётных систем, а не под идеальный случай:

1. Состав, аллергены, вес, острота и время отдачи — ОПЦИОНАЛЬНЫ. Заведения часто
   не заполняют техкарты, и оба вендора отдают эти поля как придётся.
   `None` означает «данных нет», пустой список — «проверено, ничего нет».
   Разница юридически значима: по аллергенам ассистент обязан сказать
   «данных нет, уточните на кухне», а не промолчать и не додумать.
2. Стоп-лист — отдельный, более живой поток, а не флаг внутри позиции. У iiko он
   приходит событийно, у R-Keeper — только опросом, поэтому порт нейтрален
   к способу обновления: реализация сама решает, push у неё или polling.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class MenuItemData:
    """Позиция меню в том виде, в каком её отдаёт источник."""

    external_id: str
    name: str
    category: str | None
    price: Decimal | None
    # Ниже — всё, чего может не быть. None ≠ пустое значение.
    composition: str | None = None
    allergens: tuple[str, ...] | None = None
    spiciness: int | None = None  # 0–3, шкала заведения
    weight_grams: int | None = None
    prep_time_minutes: int | None = None

    @property
    def allergens_known(self) -> bool:
        """Можно ли отвечать гостю про аллергены по этой позиции."""
        return self.allergens is not None


@dataclass(frozen=True)
class StopListEntryData:
    """Позиция, снятая с продажи прямо сейчас."""

    external_id: str
    since: datetime
    reason: str | None = None


class MenuSourcePort(Protocol):
    """Источник номенклатуры и стоп-листа для точки."""

    async def fetch_items(self, venue_id: int) -> list[MenuItemData]: ...

    async def fetch_stop_list(self, venue_id: int) -> list[StopListEntryData]: ...

    @property
    def source_name(self) -> str:
        """Кто источник: manual, csv, iiko, rkeeper — попадает в аудит изменений."""
        ...
