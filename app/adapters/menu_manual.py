"""Реализация MenuSourcePort поверх ручного ввода/CSV-импорта в нашей БД.

source_name="manual" попадает в аудит изменений (см. докстринг порта). Смысл
отдельного адаптера — в том, что домен и голосовой сценарий (app/services/
assistant_flow.py) вызывают порт, а не эту БД напрямую: когда появится адаптер
iiko/R-Keeper, он встанет сюда же, без единой правки в domain/ или в сценарии.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.ports.menu import MenuItemData, StopListEntryData
from app.services import menu as menu_service


class ManualMenuSource:
    """Меню и стоп-лист точки из собственной БД (ручной ввод + CSV, spec §2/§8).

    Структурно реализует MenuSourcePort (Protocol, см. app/ports/menu.py) —
    как и остальные адаптеры в проекте (см. app/adapters/yandex/translation.py),
    без явного наследования: порты здесь — контракт по форме, не по иерархии.
    venue_id приходит в каждый вызов (а не в конструктор) — так же, как в порту.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def source_name(self) -> str:
        return "manual"

    async def fetch_items(self, venue_id: int) -> list[MenuItemData]:
        return await menu_service.load_menu(self._session, venue_id)

    async def fetch_stop_list(self, venue_id: int) -> list[StopListEntryData]:
        return await menu_service.list_active_stop_entries(self._session, venue_id)
