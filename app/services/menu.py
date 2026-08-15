"""Доступ к меню и стоп-листу поверх ORM-моделей (spec §8, §9).

Слой не знает про FastAPI и HTTP — сигнатуры простые (сессия + примитивы/
dataclass'ы), чтобы этот модуль мог дёргать и REST-роут, и голосовой роут
(app/services/assistant_flow.py грузит меню и стоп-лист именно отсюда).

Три причины, по которым здесь несколько похожих функций чтения стоп-листа,
а не одна:
  - `active_stop_list` — только external_id, самый горячий путь (проверка на
    каждый вопрос ассистента про блюдо, spec §8);
  - `list_active_stop_entries` — то же самое, но в форме порта
    (`StopListEntryData`) для `MenuSourcePort.fetch_stop_list`;
  - `stop_list_view` — для кабинета управляющего, с именем блюда и историей.

Различие None и пустого значения в техкарте (composition/allergens/...) —
принципиальное требование порта (app/ports/menu.py) и легально значимо для
аллергенов (spec §5 S2): NULL значит "не проверялось", а не "ничего нет".
Импорт файла меню (нижняя часть этого файла — сопоставление с БД; сам разбор
CSV/Excel — в app/services/menu_import.py) обязан различать эти два случая
на входе, а не только модель на выходе.
"""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.menu_item import MenuItem
from app.db.models.stop_list_entry import StopListEntry
from app.ports.menu import MenuItemData, StopListEntryData
from app.services.menu_import import MenuCsvRow, MenuImportError, parse_menu_file  # noqa: F401

# MenuCsvRow и MenuImportError импортированы, а не определены здесь — сам разбор
# файла (CSV/Excel) переехал в app/services/menu_import.py, но app/api/menu.py,
# scripts/seed_venue.py и тесты продолжают брать их как menu_service.MenuCsvRow /
# menu_service.MenuImportError, поэтому оставляем имена доступными и тут.

_KOPECKS_PER_UNIT = 100


class MenuServiceError(Exception):
    """Базовая ошибка сервиса меню/стоп-листа."""


class MenuItemNotFoundError(MenuServiceError):
    def __init__(self, menu_item_id: int) -> None:
        super().__init__(f"Позиция меню {menu_item_id} не найдена")
        self.menu_item_id = menu_item_id


class DuplicateMenuItemNameError(MenuServiceError):
    """Название занято ВНУТРИ раздела. Одно название в разных разделах — норма
    («Чай облепиховый» в чайниках и порционно), конфликтом это не считается."""

    def __init__(self, name: str, category: str = "") -> None:
        где = f"в разделе «{category}»" if category else "в меню без раздела"
        super().__init__(f"Позиция «{name}» уже есть {где}")
        self.name = name
        self.category = category


class NotOnStopListError(MenuServiceError):
    def __init__(self, menu_item_id: int) -> None:
        super().__init__(f"Позиция {menu_item_id} сейчас не в стоп-листе")
        self.menu_item_id = menu_item_id


# --- Цена: БД хранит копейки (int), порт и API оперируют рублями (Decimal). ---
# Никакого float на этом пути — иначе копится ошибка округления на каждой правке.


def price_to_decimal(price_kopecks: int) -> Decimal:
    """Копейки из БД -> рубли для порта/API."""
    return (Decimal(price_kopecks) / _KOPECKS_PER_UNIT).quantize(Decimal("0.01"))


def price_to_kopecks(price: Decimal) -> int:
    """Рубли из API/CSV -> копейки для БД. Округление до копейки — банковское неуместно,
    здесь обычное арифметическое (ROUND_HALF_UP): цена — не бухгалтерский расчёт остатка."""
    kopecks = (price * _KOPECKS_PER_UNIT).to_integral_value(rounding=ROUND_HALF_UP)
    return int(kopecks)


# --- Чтение меню для ассистента (MenuSourcePort) -----------------------------


def _to_menu_item_data(item: MenuItem) -> MenuItemData:
    return MenuItemData(
        external_id=str(item.id),
        name=item.name,
        category=item.category or None,
        price=price_to_decimal(item.price),
        composition=item.composition,
        allergens=tuple(item.allergens) if item.allergens is not None else None,
        spiciness=item.spiciness,
        weight_grams=item.portion_weight_g,
        prep_time_minutes=item.prep_time_minutes,
    )


async def load_menu(session: AsyncSession, venue_id: int) -> list[MenuItemData]:
    """Активные (не удалённые) позиции точки в форме контракта порта."""
    rows = (
        await session.execute(
            select(MenuItem).where(MenuItem.venue_id == venue_id, MenuItem.deleted_at.is_(None))
        )
    ).scalars().all()
    return [_to_menu_item_data(row) for row in rows]


async def active_stop_list(session: AsyncSession, venue_id: int) -> frozenset[str]:
    """external_id позиций, снятых с продажи прямо сейчас. Горячий путь ассистента."""
    ids = (
        await session.execute(
            select(StopListEntry.menu_item_id).where(
                StopListEntry.venue_id == venue_id,
                StopListEntry.unset_at.is_(None),
            )
        )
    ).scalars().all()
    return frozenset(str(menu_item_id) for menu_item_id in ids)


async def list_active_stop_entries(
    session: AsyncSession, venue_id: int
) -> list[StopListEntryData]:
    """То же, что active_stop_list, но в форме StopListEntryData — для
    MenuSourcePort.fetch_stop_list."""
    rows = (
        await session.execute(
            select(StopListEntry).where(
                StopListEntry.venue_id == venue_id,
                StopListEntry.unset_at.is_(None),
            )
        )
    ).scalars().all()
    return [
        StopListEntryData(external_id=str(row.menu_item_id), since=row.set_at, reason=row.reason)
        for row in rows
    ]


# --- Стоп-лист: постановка/снятие с историей (spec §5 S4) --------------------


async def _get_owned_menu_item(
    session: AsyncSession, venue_id: int, menu_item_id: int, *, include_deleted: bool = False
) -> MenuItem:
    """Позиция точки по id. Чужая точка или удалённая позиция — как "не найдено":
    сотрудник одной точки не должен даже узнать, существует ли id в чужой (spec §5)."""
    item = await session.get(MenuItem, menu_item_id)
    if (
        item is None
        or item.venue_id != venue_id
        or (not include_deleted and item.deleted_at is not None)
    ):
        raise MenuItemNotFoundError(menu_item_id)
    return item


async def _find_active_stop_entry(
    session: AsyncSession, venue_id: int, menu_item_id: int
) -> StopListEntry | None:
    return (
        await session.execute(
            select(StopListEntry).where(
                StopListEntry.venue_id == venue_id,
                StopListEntry.menu_item_id == menu_item_id,
                StopListEntry.unset_at.is_(None),
            )
        )
    ).scalars().first()


async def set_stop(
    session: AsyncSession,
    *,
    venue_id: int,
    menu_item_id: int,
    employee_id: int,
    reason: str | None = None,
) -> StopListEntry:
    """Поставить позицию в стоп. Идемпотентно: повторное нажатие не плодит дубликаты
    строк истории, а возвращает уже существующую активную запись."""
    await _get_owned_menu_item(session, venue_id, menu_item_id)
    existing = await _find_active_stop_entry(session, venue_id, menu_item_id)
    if existing is not None:
        return existing
    entry = StopListEntry(
        venue_id=venue_id,
        menu_item_id=menu_item_id,
        set_by_employee_id=employee_id,
        reason=reason,
    )
    session.add(entry)
    await session.flush()
    await session.refresh(entry)
    return entry


async def unset_stop(
    session: AsyncSession,
    *,
    venue_id: int,
    menu_item_id: int,
    employee_id: int,
) -> StopListEntry:
    """Снять позицию со стопа. Если позиция сейчас не в стопе — ошибка, а не тихий no-op:
    управляющий должен видеть, что его нажатие ни на что не повлияло."""
    await _get_owned_menu_item(session, venue_id, menu_item_id, include_deleted=True)
    entry = await _find_active_stop_entry(session, venue_id, menu_item_id)
    if entry is None:
        raise NotOnStopListError(menu_item_id)
    entry.unset_at = datetime.now(UTC)
    entry.unset_by_employee_id = employee_id
    await session.flush()
    await session.refresh(entry)
    return entry


async def stop_list_view(
    session: AsyncSession,
    venue_id: int,
    *,
    history: bool = False,
    menu_item_id: int | None = None,
    limit: int = 200,
) -> list[tuple[StopListEntry, str]]:
    """Стоп-лист для кабинета управляющего — с именем блюда, без похода на клиента
    за отдельным запросом. history=False — только активные записи (сейчас в стопе);
    history=True — вся история постановок/снятий, самые свежие сверху."""
    stmt = (
        select(StopListEntry, MenuItem.name)
        .join(MenuItem, MenuItem.id == StopListEntry.menu_item_id)
        .where(StopListEntry.venue_id == venue_id)
    )
    if not history:
        stmt = stmt.where(StopListEntry.unset_at.is_(None))
    if menu_item_id is not None:
        stmt = stmt.where(StopListEntry.menu_item_id == menu_item_id)
    stmt = stmt.order_by(StopListEntry.set_at.desc()).limit(limit)
    rows = (await session.execute(stmt)).all()
    return [(row[0], row[1]) for row in rows]


# --- CRUD позиций меню -------------------------------------------------------


async def _find_active(
    session: AsyncSession, venue_id: int, name: str, category: str | None
) -> MenuItem | None:
    """Позиция точки по названию И разделу — так же, как её опознаёт уникальный
    индекс (ux_menu_items_venue_name_category_active). Одно название в разных
    разделах — разные позиции с разной ценой, а не дубликат."""
    return (
        await session.execute(
            select(MenuItem).where(
                MenuItem.venue_id == venue_id,
                MenuItem.name == name,
                MenuItem.category == (category or ""),
                MenuItem.deleted_at.is_(None),
            )
        )
    ).scalars().first()


async def list_menu_items(session: AsyncSession, venue_id: int) -> list[MenuItem]:
    """Позиции точки для кабинета управляющего (полные ORM-строки, с id)."""
    stmt = (
        select(MenuItem)
        .where(MenuItem.venue_id == venue_id, MenuItem.deleted_at.is_(None))
        .order_by(MenuItem.category, MenuItem.name)
    )
    return list((await session.execute(stmt)).scalars().all())


async def create_menu_item(
    session: AsyncSession,
    venue_id: int,
    *,
    name: str,
    category: str | None = None,
    price: Decimal,
    composition: str | None = None,
    allergens: tuple[str, ...] | None = None,
    spiciness: int | None = None,
    weight_grams: int | None = None,
    prep_time_minutes: int | None = None,
) -> MenuItem:
    if await _find_active(session, venue_id, name, category) is not None:
        raise DuplicateMenuItemNameError(name, category or "")
    item = MenuItem(
        venue_id=venue_id,
        name=name,
        category=category or "",
        price=price_to_kopecks(price),
        composition=composition,
        allergens=list(allergens) if allergens is not None else None,
        spiciness=spiciness,
        portion_weight_g=weight_grams,
        prep_time_minutes=prep_time_minutes,
    )
    session.add(item)
    await session.flush()
    await session.refresh(item)
    return item


# Поля, которые можно менять через PATCH/импорт. Явный список — защита от
# опечатки в ключе патча, которая молча ничего не изменит.
_PATCHABLE_FIELDS = frozenset(
    {
        "name",
        "category",
        "price",
        "composition",
        "allergens",
        "spiciness",
        "weight_grams",
        "prep_time_minutes",
    }
)


async def update_menu_item(
    session: AsyncSession, venue_id: int, menu_item_id: int, changes: dict
) -> MenuItem:
    """Частичное обновление позиции. `changes` — только реально переданные поля
    (см. Pydantic exclude_unset в app/api/menu.py): отсутствие ключа значит
    "не трогать", а не "сбросить в NULL". Для техкарты (composition/allergens/...)
    явный `None` в значении — осознанный сброс в "данных нет", это разрешено;
    для name/price явный None — ошибка (в БД они NOT NULL)."""
    item = await _get_owned_menu_item(session, venue_id, menu_item_id)
    unknown = set(changes) - _PATCHABLE_FIELDS
    if unknown:
        raise ValueError(f"Неизвестные поля патча: {sorted(unknown)}")

    # Название и раздел проверяем вместе: занятость определяет пара, и сменить
    # позиции раздел на тот, где её тёзка уже стоит, — такой же конфликт, как
    # переименование. Проверяем итоговую пару, а не то поле, которое пришло.
    if "name" in changes or "category" in changes:
        new_name = changes.get("name", item.name)
        if not new_name:
            raise ValueError("Название позиции не может быть пустым")
        new_category = (
            (changes["category"] or "") if "category" in changes else item.category
        )
        duplicate = await _find_active(session, venue_id, new_name, new_category)
        if duplicate is not None and duplicate.id != item.id:
            raise DuplicateMenuItemNameError(new_name, new_category)
        item.name = new_name
        item.category = new_category
    if "price" in changes:
        if changes["price"] is None:
            raise ValueError("Цена не может быть пустой")
        item.price = price_to_kopecks(changes["price"])
    if "composition" in changes:
        item.composition = changes["composition"]
    if "allergens" in changes:
        allergens = changes["allergens"]
        item.allergens = list(allergens) if allergens is not None else None
    if "spiciness" in changes:
        item.spiciness = changes["spiciness"]
    if "weight_grams" in changes:
        item.portion_weight_g = changes["weight_grams"]
    if "prep_time_minutes" in changes:
        item.prep_time_minutes = changes["prep_time_minutes"]

    await session.flush()
    await session.refresh(item)
    return item


async def soft_delete_menu_item(session: AsyncSession, venue_id: int, menu_item_id: int) -> None:
    """Мягкое удаление: реплики/стоп-лист/аналитика пилота ссылаются на позицию
    и не должны сломаться (FK ondelete=RESTRICT, см. app/db/models/menu_item.py)."""
    item = await _get_owned_menu_item(session, venue_id, menu_item_id)
    item.deleted_at = datetime.now(UTC)
    await session.flush()


# --- Импорт файла меню: сопоставление с БД и применение ----------------------
#
# Сам разбор файла (CSV/Excel, кодировка, поиск шапки, алиасы колонок) —
# в app/services/menu_import.py, отдельным модулем без БД (см. его докстринг).
# Здесь — то, что этому модулю принципиально недоступно: сопоставление
# разобранных строк с уже существующими позициями точки и запись в БД.
#
# Пустая ячейка техкарты значит "данных нет" (None) — ассистент обязан честно
# сказать "уточните на кухне" (spec §5 S2), а не промолчать и не додумать.
# Единственное исключение — аллергены: пустая ячейка тоже None, но явное слово
# "нет"/"нету"/"отсутствуют" в ячейке — это подтверждённый факт "аллергенов
# нет" (allergens=()), и это юридически другое утверждение, чем "не
# проверялось" (см. app/ports/menu.py, app/services/menu_import.py).


@dataclass(frozen=True)
class MenuImportPlanItem:
    row: MenuCsvRow
    menu_item_id: int


@dataclass(frozen=True)
class MenuImportPlan:
    """Итог разбора и сопоставления с текущим меню точки. При dry_run=True (applied=False)
    ничего не записано в БД — управляющий должен увидеть план ДО применения (spec)."""

    to_create: list[MenuCsvRow] = field(default_factory=list)
    to_update: list[MenuImportPlanItem] = field(default_factory=list)
    rejected: list[MenuCsvRow] = field(default_factory=list)
    applied: bool = False


async def build_menu_import_plan(
    session: AsyncSession, venue_id: int, parsed_rows: list[MenuCsvRow]
) -> MenuImportPlan:
    """Сопоставить разобранные строки с текущим меню точки: что создастся,
    что обновится, что отклонено. Не пишет в БД — вызывающий решает, применять ли."""
    rejected = [row for row in parsed_rows if not row.is_valid]
    valid_rows = [row for row in parsed_rows if row.is_valid]

    # Дубликат внутри самого файла — конфликт между строками, а не ошибка
    # конкретной строки: держим первую, остальные явно отклоняем. Дубликатом
    # считается повтор пары «название + раздел»: одно название в разных
    # разделах — это разные позиции меню с разной ценой, и обе нужны.
    seen: dict[tuple[str, str], MenuCsvRow] = {}
    deduped: list[MenuCsvRow] = []
    for row in valid_rows:
        ключ = (row.name, row.category or "")
        earlier = seen.get(ключ)
        if earlier is not None:
            где = f" в разделе «{row.category}»" if row.category else ""
            rejected.append(
                replace(
                    row,
                    errors=(
                        f"дубликат названия{где} в файле "
                        f"(уже строка {earlier.line_number})",
                    ),
                )
            )
            continue
        seen[ключ] = row
        deduped.append(row)

    to_create: list[MenuCsvRow] = []
    to_update: list[MenuImportPlanItem] = []
    for row in deduped:
        existing = await _find_active(session, venue_id, row.name, row.category)
        if existing is None:
            to_create.append(row)
        else:
            to_update.append(MenuImportPlanItem(row=row, menu_item_id=existing.id))

    return MenuImportPlan(
        to_create=to_create, to_update=to_update, rejected=rejected, applied=False
    )


async def apply_menu_import_plan(
    session: AsyncSession, venue_id: int, plan: MenuImportPlan
) -> MenuImportPlan:
    """Применить план (созданный build_menu_import_plan) — реально пишет в БД."""
    for row in plan.to_create:
        assert row.price is not None  # гарантировано is_valid в build_menu_import_plan
        await create_menu_item(
            session,
            venue_id,
            name=row.name,
            category=row.category,
            price=row.price,
            composition=row.composition,
            allergens=row.allergens,
            spiciness=row.spiciness,
            weight_grams=row.weight_grams,
            prep_time_minutes=row.prep_time_minutes,
        )
    for plan_item in plan.to_update:
        row = plan_item.row
        assert row.price is not None
        await update_menu_item(
            session,
            venue_id,
            plan_item.menu_item_id,
            {
                "category": row.category,
                "price": row.price,
                "composition": row.composition,
                "allergens": row.allergens,
                "spiciness": row.spiciness,
                "weight_grams": row.weight_grams,
                "prep_time_minutes": row.prep_time_minutes,
            },
        )
    await session.flush()
    return replace(plan, applied=True)


async def import_menu_csv(
    session: AsyncSession,
    venue_id: int,
    raw: bytes,
    *,
    dry_run: bool,
    filename: str | None = None,
) -> MenuImportPlan:
    """Точка входа импорта: разобрать -> сопоставить с БД -> (если не dry-run) применить.

    Имя не в сигнатуре сохранилось историческим ("csv"), хотя файл может быть и
    Excel (.xlsx) — формат определяется по содержимому в parse_menu_file, не по
    имени функции. `filename` опционален и нужен только для текста ошибки
    (scripts/seed_venue.py его не передаёт и продолжает работать как раньше).

    dry_run=True — только план, ничего не меняется (управляющий видит, что создастся
    и что обновится, до применения). dry_run=False — план тут же применяется."""
    parsed_rows = parse_menu_file(raw, filename=filename)
    plan = await build_menu_import_plan(session, venue_id, parsed_rows)
    if dry_run:
        return plan
    return await apply_menu_import_plan(session, venue_id, plan)
