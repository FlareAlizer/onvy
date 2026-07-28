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
Импорт CSV (нижняя часть файла) обязан различать эти два случая на входе,
а не только модель на выходе.
"""

import csv
import io
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.menu_item import MenuItem
from app.db.models.stop_list_entry import StopListEntry
from app.ports.menu import MenuItemData, StopListEntryData

_KOPECKS_PER_UNIT = 100


class MenuServiceError(Exception):
    """Базовая ошибка сервиса меню/стоп-листа."""


class MenuItemNotFoundError(MenuServiceError):
    def __init__(self, menu_item_id: int) -> None:
        super().__init__(f"Позиция меню {menu_item_id} не найдена")
        self.menu_item_id = menu_item_id


class DuplicateMenuItemNameError(MenuServiceError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Позиция с названием «{name}» уже есть в меню точки")
        self.name = name


class NotOnStopListError(MenuServiceError):
    def __init__(self, menu_item_id: int) -> None:
        super().__init__(f"Позиция {menu_item_id} сейчас не в стоп-листе")
        self.menu_item_id = menu_item_id


class MenuImportError(MenuServiceError):
    """Файл целиком нечитаем: не CSV, неизвестная кодировка, нет нужных колонок."""


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


async def _find_active_by_name(session: AsyncSession, venue_id: int, name: str) -> MenuItem | None:
    return (
        await session.execute(
            select(MenuItem).where(
                MenuItem.venue_id == venue_id,
                MenuItem.name == name,
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
    if await _find_active_by_name(session, venue_id, name) is not None:
        raise DuplicateMenuItemNameError(name)
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

    if "name" in changes:
        new_name = changes["name"]
        if not new_name:
            raise ValueError("Название позиции не может быть пустым")
        duplicate = await _find_active_by_name(session, venue_id, new_name)
        if duplicate is not None and duplicate.id != item.id:
            raise DuplicateMenuItemNameError(new_name)
        item.name = new_name
    if "category" in changes:
        item.category = changes["category"] or ""
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


# --- Импорт CSV: разбор (чистая логика, без БД) ------------------------------
#
# Колонки (по заголовку, порядок в файле не важен): название, категория, цена,
# состав, аллергены, вес, время отдачи, острота. Пустая ячейка техкарты значит
# "данных нет" (None) — ассистент обязан честно сказать "уточните на кухне"
# (spec §5 S2), а не промолчать и не додумать. Единственное исключение —
# аллергены: пустая ячейка тоже None, но явное слово "нет"/"нету"/"отсутствуют"
# в ячейке — это подтверждённый факт "аллергенов нет" (allergens=()), и это
# юридически другое утверждение, чем "не проверялось" (см. app/ports/menu.py).

_HEADER_ALIASES: dict[str, str] = {
    "название": "name",
    "наименование": "name",
    "блюдо": "name",
    "категория": "category",
    "цена": "price",
    "состав": "composition",
    "аллергены": "allergens",
    "вес": "weight_grams",
    "вес, г": "weight_grams",
    "время отдачи": "prep_time_minutes",
    "время приготовления": "prep_time_minutes",
    "острота": "spiciness",
}

# Только однозначные утвердительные слова — "без" отдельно не берём: "без глютена"
# в свободном тексте значило бы другое, а как значение всей ячейки — слишком
# двусмысленно, чтобы автоматически считать это подтверждением "аллергенов нет".
_NO_ALLERGENS_WORDS = frozenset({"нет", "нету", "отсутствуют"})


@dataclass(frozen=True)
class MenuCsvRow:
    """Одна разобранная строка файла. errors непусто — строка не будет применена."""

    line_number: int
    name: str
    category: str | None
    price: Decimal | None
    composition: str | None
    allergens: tuple[str, ...] | None
    spiciness: int | None
    weight_grams: int | None
    prep_time_minutes: int | None
    errors: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.errors


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


def decode_menu_csv(raw: bytes) -> str:
    """Декодировать CSV. Приоритет UTF-8: если сотрудник выгрузил файл сам, это чаще
    всего он. CP1251 — второй в очереди осознанно: это реальный случай экспорта из
    Excel под русской Windows (разделитель там обычно ";"), а не гипотетический."""
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise MenuImportError("Не удалось определить кодировку файла (ожидается UTF-8 или CP1251)")


def _sniff_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=";,").delimiter
    except csv.Error:
        # Короткий/однострочный файл — Sniffer не справляется. По умолчанию ";":
        # это разделитель Excel под русской локалью, самый вероятный реальный случай.
        return ";" if sample.count(";") >= sample.count(",") else ","


def _parse_optional_int(
    raw: str, *, field_name: str, errors: list[str], min_value: int | None = None,
    max_value: int | None = None,
) -> int | None:
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        errors.append(f"не удалось разобрать «{field_name}»: {raw!r}")
        return None
    too_small = min_value is not None and value < min_value
    too_large = max_value is not None and value > max_value
    if too_small or too_large:
        errors.append(f"«{field_name}» вне диапазона {min_value}..{max_value}: {value}")
        return None
    return value


def _parse_row(line_number: int, values: dict[str, str]) -> MenuCsvRow:
    errors: list[str] = []

    name = values.get("name", "")
    if not name:
        errors.append("не заполнено название")

    category = values.get("category") or None

    price_raw = values.get("price", "")
    price: Decimal | None = None
    if not price_raw:
        errors.append("не заполнена цена")
    else:
        try:
            price = Decimal(price_raw.replace(",", "."))
        except InvalidOperation:
            errors.append(f"не удалось разобрать цену: {price_raw!r}")
        else:
            if price < 0:
                errors.append(f"цена не может быть отрицательной: {price_raw!r}")
                price = None

    composition = values.get("composition") or None

    allergens_raw = values.get("allergens", "")
    allergens: tuple[str, ...] | None
    if not allergens_raw:
        allergens = None
    elif allergens_raw.strip().casefold() in _NO_ALLERGENS_WORDS:
        allergens = ()
    else:
        allergens = tuple(a.strip() for a in allergens_raw.split(",") if a.strip())

    spiciness = _parse_optional_int(
        values.get("spiciness", ""), field_name="острота", errors=errors, min_value=0, max_value=3
    )
    weight_grams = _parse_optional_int(
        values.get("weight_grams", ""), field_name="вес", errors=errors, min_value=0
    )
    prep_time_minutes = _parse_optional_int(
        values.get("prep_time_minutes", ""), field_name="время отдачи", errors=errors, min_value=0
    )

    return MenuCsvRow(
        line_number=line_number,
        name=name,
        category=category,
        price=price,
        composition=composition,
        allergens=allergens,
        spiciness=spiciness,
        weight_grams=weight_grams,
        prep_time_minutes=prep_time_minutes,
        errors=tuple(errors),
    )


def parse_menu_csv(raw: bytes) -> list[MenuCsvRow]:
    """Разобрать файл в список строк. Чистая функция — без БД, без FastAPI,
    легко проверяется юнит-тестами (см. tests/test_menu_import.py)."""
    text = decode_menu_csv(raw)
    delimiter = _sniff_delimiter(text[:2048])
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    if not rows:
        raise MenuImportError("Файл пуст")

    header = [cell.strip().casefold() for cell in rows[0]]
    column_map: dict[int, str] = {}
    for idx, cell in enumerate(header):
        mapped = _HEADER_ALIASES.get(cell)
        if mapped:
            column_map[idx] = mapped

    present_fields = set(column_map.values())
    if "name" not in present_fields:
        raise MenuImportError("В файле нет обязательной колонки «название»")
    if "price" not in present_fields:
        raise MenuImportError("В файле нет обязательной колонки «цена»")

    parsed: list[MenuCsvRow] = []
    for line_number, raw_row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in raw_row):
            continue  # полностью пустая строка — не ошибка данных, просто пропуск
        values = {
            field_name: (raw_row[idx].strip() if idx < len(raw_row) else "")
            for idx, field_name in column_map.items()
        }
        parsed.append(_parse_row(line_number, values))
    return parsed


# --- Импорт CSV: применение к БД --------------------------------------------


async def build_menu_import_plan(
    session: AsyncSession, venue_id: int, parsed_rows: list[MenuCsvRow]
) -> MenuImportPlan:
    """Сопоставить разобранные строки с текущим меню точки: что создастся,
    что обновится, что отклонено. Не пишет в БД — вызывающий решает, применять ли."""
    rejected = [row for row in parsed_rows if not row.is_valid]
    valid_rows = [row for row in parsed_rows if row.is_valid]

    # Дубликат названия внутри самого файла — конфликт между строками, а не
    # ошибка конкретной строки: держим первую, остальные явно отклоняем.
    seen: dict[str, MenuCsvRow] = {}
    deduped: list[MenuCsvRow] = []
    for row in valid_rows:
        earlier = seen.get(row.name)
        if earlier is not None:
            rejected.append(
                replace(
                    row,
                    errors=(f"дубликат названия в файле (уже строка {earlier.line_number})",),
                )
            )
            continue
        seen[row.name] = row
        deduped.append(row)

    to_create: list[MenuCsvRow] = []
    to_update: list[MenuImportPlanItem] = []
    for row in deduped:
        existing = await _find_active_by_name(session, venue_id, row.name)
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
    session: AsyncSession, venue_id: int, raw: bytes, *, dry_run: bool
) -> MenuImportPlan:
    """Точка входа импорта: разобрать -> сопоставить с БД -> (если не dry-run) применить.

    dry_run=True — только план, ничего не меняется (управляющий видит, что создастся
    и что обновится, до применения). dry_run=False — план тут же применяется."""
    parsed_rows = parse_menu_csv(raw)
    plan = await build_menu_import_plan(session, venue_id, parsed_rows)
    if dry_run:
        return plan
    return await apply_menu_import_plan(session, venue_id, plan)
