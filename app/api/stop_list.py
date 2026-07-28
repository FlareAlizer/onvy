"""REST стоп-листа точки (spec §5 S4): поставить, снять, посмотреть активный
список и историю.

S4 требует, чтобы действие управляющего занимало секунды — отсюда предельно
простые эндпоинты постановки/снятия: id позиции в пути, необязательная причина
в теле, и всё. Чтение активного стоп-листа открыто любому сотруднику точки (тот
же принцип видимости, что у меню): официант должен иметь возможность свериться,
даже если голосовой ассистент недоступен. Изменение стоп-листа и история —
только управляющему.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.menu import _check_venue
from app.db import get_session
from app.db.models.stop_list_entry import StopListEntry
from app.deps import CurrentEmployee, require_employee, require_manager
from app.schemas.menu import StopListActionIn, StopListEntryOut
from app.services import menu as menu_service

router = APIRouter(prefix="/venues/{venue_id}/stop-list", tags=["stop-list"])


def _map_entry(entry: StopListEntry, menu_item_name: str) -> StopListEntryOut:
    return StopListEntryOut(
        id=entry.id,
        menu_item_id=entry.menu_item_id,
        menu_item_name=menu_item_name,
        set_at=entry.set_at,
        unset_at=entry.unset_at,
        set_by_employee_id=entry.set_by_employee_id,
        unset_by_employee_id=entry.unset_by_employee_id,
        reason=entry.reason,
    )


@router.get("", response_model=list[StopListEntryOut])
async def active_stop_list(
    venue_id: int,
    current: CurrentEmployee = Depends(require_employee),
    db: AsyncSession = Depends(get_session),
) -> list[StopListEntryOut]:
    """Что сейчас снято с продажи — видно любому сотруднику точки."""
    _check_venue(current, venue_id)
    rows = await menu_service.stop_list_view(db, venue_id, history=False)
    return [_map_entry(entry, name) for entry, name in rows]


@router.get("/history", response_model=list[StopListEntryOut])
async def stop_list_history(
    venue_id: int,
    menu_item_id: int | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> list[StopListEntryOut]:
    """Полная история постановок/снятий — аналитика пилота (spec §4 S6), только управляющий."""
    _check_venue(current, venue_id)
    rows = await menu_service.stop_list_view(
        db, venue_id, history=True, menu_item_id=menu_item_id, limit=limit
    )
    return [_map_entry(entry, name) for entry, name in rows]


@router.post("/{menu_item_id}/set", response_model=StopListEntryOut, status_code=status.HTTP_201_CREATED)
async def set_stop(
    venue_id: int,
    menu_item_id: int,
    payload: StopListActionIn = StopListActionIn(),
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> StopListEntryOut:
    """Поставить позицию в стоп. Идемпотентно: повторный вызов на уже стоящей
    позиции не плодит вторую запись — возвращает существующую."""
    _check_venue(current, venue_id)
    try:
        entry = await menu_service.set_stop(
            db,
            venue_id=venue_id,
            menu_item_id=menu_item_id,
            employee_id=current.id,
            reason=payload.reason,
        )
    except menu_service.MenuItemNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Позиция не найдена") from exc
    await db.commit()
    rows = await menu_service.stop_list_view(db, venue_id, history=True, menu_item_id=menu_item_id, limit=1)
    name = rows[0][1] if rows else ""
    return _map_entry(entry, name)


@router.post("/{menu_item_id}/unset", response_model=StopListEntryOut)
async def unset_stop(
    venue_id: int,
    menu_item_id: int,
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> StopListEntryOut:
    """Снять позицию со стопа. Если позиция сейчас не в стопе — 409, а не тихий успех:
    управляющий должен видеть, что нажатие ни на что не повлияло."""
    _check_venue(current, venue_id)
    try:
        entry = await menu_service.unset_stop(
            db, venue_id=venue_id, menu_item_id=menu_item_id, employee_id=current.id
        )
    except menu_service.MenuItemNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Позиция не найдена") from exc
    except menu_service.NotOnStopListError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await db.commit()
    rows = await menu_service.stop_list_view(db, venue_id, history=True, menu_item_id=menu_item_id, limit=1)
    name = rows[0][1] if rows else ""
    return _map_entry(entry, name)
