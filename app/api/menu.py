"""REST меню точки: список/создание/редактирование/мягкое удаление, импорт CSV.

Роуты тонкие: разобрать вход -> проверить права -> вызвать app.services.menu ->
смаппить ответ. Вся бизнес-логика (конвертация цены, разбор CSV, правила
аллергенов) — в сервисе, не здесь.

Права (spec §5, п.5 задания): смотреть меню может любой аутентифицированный
сотрудник СВОЕЙ точки; создавать/редактировать/удалять и импортировать —
только управляющий. venue_id в пути всегда сверяется с venue_id из токена —
сотрудник одной точки не должен ни увидеть, ни изменить чужую (см. require_own_venue).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.db.models.menu_item import MenuItem
from app.deps import CurrentEmployee, require_employee, require_manager
from app.schemas.menu import (
    MenuImportPreviewOut,
    MenuImportRowOut,
    MenuImportUpdateRowOut,
    MenuItemIn,
    MenuItemOut,
    MenuItemPatch,
)
from app.services import menu as menu_service
from app.services.menu import MenuCsvRow

router = APIRouter(prefix="/venues/{venue_id}/menu", tags=["menu"])


def require_own_venue(current: CurrentEmployee, venue_id: int) -> None:
    """Отказ, а не молчаливая переадресация: сотруднику одной точки нечего делать
    в данных другой, даже если он знает её id. Используется и здесь, и в
    app/api/stop_list.py — venue-скоуп у меню и стоп-листа один и тот же."""
    if current.venue_id != venue_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Точка недоступна этому сотруднику"
        )


def _map_item(item: MenuItem) -> MenuItemOut:
    return MenuItemOut(
        id=item.id,
        name=item.name,
        category=item.category or None,
        price=menu_service.price_to_decimal(item.price),
        composition=item.composition,
        allergens=list(item.allergens) if item.allergens is not None else None,
        spiciness=item.spiciness,
        weight_grams=item.portion_weight_g,
        prep_time_minutes=item.prep_time_minutes,
    )


def _map_row(row: MenuCsvRow) -> MenuImportRowOut:
    return MenuImportRowOut(
        line_number=row.line_number,
        name=row.name,
        category=row.category,
        price=row.price,
        composition=row.composition,
        allergens=list(row.allergens) if row.allergens is not None else None,
        spiciness=row.spiciness,
        weight_grams=row.weight_grams,
        prep_time_minutes=row.prep_time_minutes,
        errors=list(row.errors),
    )


@router.get("", response_model=list[MenuItemOut])
async def list_menu(
    venue_id: int,
    current: CurrentEmployee = Depends(require_employee),
    db: AsyncSession = Depends(get_session),
) -> list[MenuItemOut]:
    """Меню точки — доступно любому аутентифицированному сотруднику этой точки."""
    require_own_venue(current, venue_id)
    items = await menu_service.list_menu_items(db, venue_id)
    return [_map_item(item) for item in items]


@router.post("", response_model=MenuItemOut, status_code=status.HTTP_201_CREATED)
async def create_menu_item(
    venue_id: int,
    payload: MenuItemIn,
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> MenuItemOut:
    require_own_venue(current, venue_id)
    try:
        item = await menu_service.create_menu_item(
            db,
            venue_id,
            name=payload.name,
            category=payload.category,
            price=payload.price,
            composition=payload.composition,
            allergens=tuple(payload.allergens) if payload.allergens is not None else None,
            spiciness=payload.spiciness,
            weight_grams=payload.weight_grams,
            prep_time_minutes=payload.prep_time_minutes,
        )
    except menu_service.DuplicateMenuItemNameError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await db.commit()
    return _map_item(item)


@router.patch("/{menu_item_id}", response_model=MenuItemOut)
async def update_menu_item(
    venue_id: int,
    menu_item_id: int,
    payload: MenuItemPatch,
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> MenuItemOut:
    """Частичное обновление: только поля, реально присутствующие в теле запроса
    (exclude_unset), правят позицию — остальные остаются как были."""
    require_own_venue(current, venue_id)
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Название не может быть null"
        )
    if "price" in changes and changes["price"] is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Цена не может быть null"
        )
    if "allergens" in changes and changes["allergens"] is not None:
        changes["allergens"] = tuple(changes["allergens"])

    try:
        item = await menu_service.update_menu_item(db, venue_id, menu_item_id, changes)
    except menu_service.MenuItemNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Позиция не найдена") from exc
    except menu_service.DuplicateMenuItemNameError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await db.commit()
    return _map_item(item)


@router.delete("/{menu_item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_menu_item(
    venue_id: int,
    menu_item_id: int,
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> None:
    require_own_venue(current, venue_id)
    try:
        await menu_service.soft_delete_menu_item(db, venue_id, menu_item_id)
    except menu_service.MenuItemNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Позиция не найдена") from exc
    await db.commit()


@router.post("/import", response_model=MenuImportPreviewOut)
async def import_menu(
    venue_id: int,
    file: UploadFile,
    dry_run: bool = Query(
        default=True,
        description="true (по умолчанию) — только показать план, ничего не менять; "
        "false — применить сразу же",
    ),
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> MenuImportPreviewOut:
    """Импорт CSV. По умолчанию dry-run: управляющий сначала видит, что создастся
    и что обновится, и только повторным вызовом с dry_run=false применяет.

    Формат: колонки «название, категория, цена, состав, аллергены, вес, время
    отдачи, острота» (порядок в файле не важен, ищем по заголовку). Кодировка —
    UTF-8 или CP1251, разделитель «,» или «;» — определяются автоматически
    (реальный случай: выгрузка из Excel под русской Windows приходит в CP1251
    с «;»). Пустая ячейка техкарты значит «данных нет»; для аллергенов явное
    слово «нет» — это «аллергенов нет» (проверено), а не то же самое, что пусто.
    """
    require_own_venue(current, venue_id)
    raw = await file.read()
    try:
        plan = await menu_service.import_menu_csv(db, venue_id, raw, dry_run=dry_run)
    except menu_service.MenuImportError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not dry_run:
        await db.commit()
    return MenuImportPreviewOut(
        to_create=[_map_row(row) for row in plan.to_create],
        to_update=[
            MenuImportUpdateRowOut(row=_map_row(item.row), menu_item_id=item.menu_item_id)
            for item in plan.to_update
        ],
        rejected=[_map_row(row) for row in plan.rejected],
        applied=plan.applied,
    )
