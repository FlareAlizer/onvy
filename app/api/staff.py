"""REST статистики/смен сотрудника и агрегации FAQ (задание лупа, пп.2-4).

Права: ростер точки и FAQ-агрегации — только управляющий; статистику и смены
сотрудник видит сам, чужие — тоже только управляющий (та же идиома self-or-
manager, что app/api/kpi.py).
"""

import logging
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.menu import require_own_venue
from app.db import get_session
from app.db.models.comm_group import CommGroup, EmployeeCommGroup
from app.db.models.employee import Employee
from app.db.models.enums import EMPLOYEE_ROLES, LANGUAGES
from app.db.seed import ROLE_GROUPS, generate_password, generate_unique_pins
from app.deps import CurrentEmployee, require_employee, require_manager
from app.domain.nicknames import check_nicknames
from app.schemas.staff import (
    EmployeeOut,
    EmployeeStatsOut,
    FaqGapOut,
    FaqTopQuestionOut,
    ShiftDetailOut,
    ShiftEventOut,
    ShiftSummaryOut,
    StaffAccessOut,
    StaffCreateRequest,
    StaffUpdateRequest,
)
from app.services import auth as auth_service
from app.services import stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/venues/{venue_id}", tags=["staff"])


def _require_self_or_manager(current: CurrentEmployee, employee_id: int) -> None:
    if current.role != "manager" and current.id != employee_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Можно смотреть только свои данные")


@router.get("/staff", response_model=list[EmployeeOut])
async def list_staff(
    venue_id: int,
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> list[EmployeeOut]:
    """Ростер точки — кабинет руководителя."""
    require_own_venue(current, venue_id)
    rows = (
        (
            await db.execute(
                select(Employee).where(Employee.venue_id == venue_id, Employee.deleted_at.is_(None))
            )
        )
        .scalars()
        .all()
    )
    return [
        EmployeeOut(
            id=e.id,
            name=e.name,
            nickname=e.nickname,
            role=e.role,
            language=e.language,
            is_active=e.is_active,
            hired_at=e.hired_at,
        )
        for e in rows
    ]


@router.get("/staff/{employee_id}/stats", response_model=EmployeeStatsOut)
async def employee_stats_endpoint(
    venue_id: int,
    employee_id: int,
    days: int = Query(default=7, ge=1, le=90),
    current: CurrentEmployee = Depends(require_employee),
    db: AsyncSession = Depends(get_session),
) -> EmployeeStatsOut:
    """EmployeeStats фронта — честная версия (задание, п.2): revenue/avg_check/
    conversion/script_compliance здесь нет, см. app/schemas/staff.py."""
    require_own_venue(current, venue_id)
    _require_self_or_manager(current, employee_id)
    since = datetime.now(UTC) - timedelta(days=days)
    result = await stats.employee_stats(db, venue_id, employee_id, since=since, period_days=days)
    return EmployeeStatsOut(
        employee_id=result.employee_id,
        period_days=result.period_days,
        dialogs=result.dialogs,
        response_sec=result.response_sec,
        autonomy_percent=result.autonomy_percent,
        help_requests=result.help_requests,
    )


@router.get("/staff/{employee_id}/shifts", response_model=list[ShiftSummaryOut])
async def employee_shifts_endpoint(
    venue_id: int,
    employee_id: int,
    days: int = Query(default=14, ge=1, le=90),
    current: CurrentEmployee = Depends(require_employee),
    db: AsyncSession = Depends(get_session),
) -> list[ShiftSummaryOut]:
    """Список смен сотрудника — честная замена ленте "диалогов" фронта (задание,
    п.3): у нас нет понятия обслуживания одного гостя, есть поток реплик/вопросов
    за смену. Подробности одной смены — GET .../shifts/{shift_date}."""
    require_own_venue(current, venue_id)
    _require_self_or_manager(current, employee_id)
    since = datetime.now(UTC) - timedelta(days=days)
    shifts = await stats.employee_shifts(db, venue_id, employee_id, since=since)
    return [
        ShiftSummaryOut(
            shift_date=s.shift_date,
            employee_id=s.employee_id,
            started_at=s.started_at,
            ended_at=s.ended_at,
            utterances_count=s.utterances_count,
            assistant_queries_count=s.assistant_queries_count,
            help_requests=s.help_requests,
            response_sec=s.response_sec,
        )
        for s in shifts
    ]


@router.get("/staff/{employee_id}/shifts/{shift_date}", response_model=ShiftDetailOut)
async def employee_shift_detail_endpoint(
    venue_id: int,
    employee_id: int,
    shift_date: date,
    current: CurrentEmployee = Depends(require_employee),
    db: AsyncSession = Depends(get_session),
) -> ShiftDetailOut:
    """Детали одной смены с транскриптом — "детали диалога" фронта (задание, п.3).
    wave/moments сознательно отсутствуют, а не отданы пустыми под видом реальных
    данных — см. app/schemas/staff.py ShiftDetailOut."""
    require_own_venue(current, venue_id)
    _require_self_or_manager(current, employee_id)
    detail = await stats.shift_detail(db, venue_id, employee_id, shift_date)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="За эту дату событий нет")
    return ShiftDetailOut(
        shift_date=detail.shift_date,
        employee_id=detail.employee_id,
        started_at=detail.started_at,
        ended_at=detail.ended_at,
        utterances_count=detail.utterances_count,
        assistant_queries_count=detail.assistant_queries_count,
        help_requests=detail.help_requests,
        response_sec=detail.response_sec,
        events=[
            ShiftEventOut(
                kind=e.kind,
                at=e.at,
                text=e.text,
                detail=e.detail,
                total_ms=e.total_ms,
                menu_item_found=e.menu_item_found,
                is_help_request=e.is_help_request,
            )
            for e in detail.events
        ],
    )


@router.get("/faq/top-questions", response_model=list[FaqTopQuestionOut])
async def faq_top_questions(
    venue_id: int,
    days: int = Query(default=30, ge=1, le=180),
    limit: int = Query(default=20, ge=1, le=100),
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> list[FaqTopQuestionOut]:
    """Частые вопросы официантов к ассистенту — база знаний FAQ, реальная
    агрегация assistant_queries (задание, п.4)."""
    require_own_venue(current, venue_id)
    since = datetime.now(UTC) - timedelta(days=days)
    rows = await stats.faq_rows(db, venue_id, since=since)
    top = stats.aggregate_top_questions(rows, now=datetime.now(UTC))[:limit]
    return [
        FaqTopQuestionOut(
            question=item.question,
            count=item.count,
            trend_percent=item.trend_percent,
            avg_response_sec=item.avg_response_sec,
            ever_answered=item.ever_answered,
            last_asked_at=item.last_asked_at,
        )
        for item in top
    ]


@router.get("/faq/gaps", response_model=list[FaqGapOut])
async def faq_gaps(
    venue_id: int,
    days: int = Query(default=30, ge=1, le=180),
    limit: int = Query(default=20, ge=1, le=100),
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> list[FaqGapOut]:
    """Вопросы, на которые ассистент не нашёл ответа в меню — самое ценное для
    управляющего: показывает дыры в техкарте/меню (задание, п.4)."""
    require_own_venue(current, venue_id)
    since = datetime.now(UTC) - timedelta(days=days)
    rows = await stats.faq_rows(db, venue_id, since=since)
    gaps = stats.aggregate_gaps(rows)[:limit]
    return [
        FaqGapOut(
            question=item.question,
            miss_count=item.miss_count,
            last_asked_at=item.last_asked_at,
            sample_query=item.sample_query,
        )
        for item in gaps
    ]


# --- Управление составом смены ----------------------------------------------------


async def _venue_menu_words(db: AsyncSession, venue_id: int) -> list[str]:
    """Названия блюд точки — по ним проверяется, что кличка не конфликтует.

    Если меню прочитать не удалось, возвращаем пустой список и проверяем кличку
    без него. Совпадение с блюдом — неприятность (вопрос про плов уедет
    человеку), а невозможность завести официанта в смену — остановка работы.
    Второе хуже, поэтому эта проверка не имеет права блокировать добавление.
    """
    from app.db.models.menu_item import MenuItem

    try:
        rows = (
            await db.execute(
                select(MenuItem.name).where(
                    MenuItem.venue_id == venue_id, MenuItem.deleted_at.is_(None)
                )
            )
        ).scalars().all()
    except SQLAlchemyError as exc:
        logger.warning(
            "Не смог прочитать меню точки %s (%s) — кличку проверяю без него",
            venue_id,
            exc,
        )
        return []
    return list(rows)


@router.post("/staff", response_model=StaffAccessOut, status_code=status.HTTP_201_CREATED)
async def create_staff(
    venue_id: int,
    payload: StaffCreateRequest,
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> StaffAccessOut:
    """Добавить человека в смену и выдать ему доступ.

    PIN генерируется всегда, пароль — только если указана почта. И то и другое
    показывается в ответе единственный раз: в базе лежат argon2id-хеши, обратно
    их не прочитать. Забыли — перевыдайте, это отдельная кнопка.
    """
    require_own_venue(current, venue_id)

    if payload.role not in EMPLOYEE_ROLES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Неизвестная роль. Допустимо: {', '.join(EMPLOYEE_ROLES)}",
        )
    if payload.language not in LANGUAGES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Неизвестный язык. Допустимо: {', '.join(LANGUAGES)}",
        )

    name = payload.name.strip()
    существующие = (
        await db.execute(
            select(Employee.name, Employee.nickname).where(
                Employee.venue_id == venue_id, Employee.deleted_at.is_(None)
            )
        )
    ).all()

    # Сотрудников различаем по имени — двух «Азизов» без уточнения не пускаем.
    if any(имя.casefold() == name.casefold() for имя, _ in существующие):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"«{name}» уже есть в смене. Добавьте фамилию или уточнение.",
        )

    if payload.nickname:
        клички = [n for _, n in существующие if n] + [payload.nickname]
        проблемы = check_nicknames(
            клички, menu_names=await _venue_menu_words(db, venue_id)
        )
        # Показываем только то, что касается новой клички: чужие проблемы,
        # если они были заведены раньше, добавлению не мешают.
        своя = [p for p in проблемы if p.nickname == payload.nickname]
        if своя:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(своя[0])
            )

    email = auth_service.normalize_email(payload.email) if payload.email else None
    if email is not None:
        занято = (
            await db.execute(
                select(Employee.id).where(
                    Employee.email == email, Employee.deleted_at.is_(None)
                )
            )
        ).scalar_one_or_none()
        if занято is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail="Эта почта уже занята"
            )

    pin = generate_unique_pins(1)[0]
    password = generate_password() if email else None

    employee = Employee(
        venue_id=venue_id,
        name=name,
        nickname=payload.nickname.strip() if payload.nickname else None,
        role=payload.role,
        language=payload.language,
        email=email,
        password_hash=auth_service.hash_password(password) if password else None,
        pin_hash=auth_service.hash_pin(pin),
    )
    db.add(employee)
    await db.flush()

    # Группы связи по роли: без них человека не будет слышно в рации.
    группы = (
        await db.execute(
            select(CommGroup.id, CommGroup.name).where(
                CommGroup.venue_id == venue_id, CommGroup.deleted_at.is_(None)
            )
        )
    ).all()
    по_имени = {имя: gid for gid, имя in группы}
    for group in ROLE_GROUPS[payload.role]:
        gid = по_имени.get(group.value)
        if gid is not None:
            db.add(EmployeeCommGroup(employee_id=employee.id, comm_group_id=gid))

    await db.commit()

    return StaffAccessOut(
        employee_id=employee.id,
        name=employee.name,
        nickname=employee.nickname,
        role=employee.role,
        language=employee.language,
        pin=pin,
        email=email,
        password=password,
    )


@router.post("/staff/{employee_id}/reset-access", response_model=StaffAccessOut)
async def reset_access(
    venue_id: int,
    employee_id: int,
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> StaffAccessOut:
    """Перевыдать PIN (и пароль, если есть почта).

    Единственный способ вернуть доступ забывшему: посмотреть старый нельзя,
    в базе только хеш. Прежние PIN и пароль сразу перестают работать.
    """
    require_own_venue(current, venue_id)

    employee = await db.get(Employee, employee_id)
    if (
        employee is None
        or employee.venue_id != venue_id
        or employee.deleted_at is not None
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")

    pin = generate_unique_pins(1)[0]
    employee.pin_hash = auth_service.hash_pin(pin)

    password = None
    if employee.email:
        password = generate_password()
        employee.password_hash = auth_service.hash_password(password)

    await db.commit()

    return StaffAccessOut(
        employee_id=employee.id,
        name=employee.name,
        nickname=employee.nickname,
        role=employee.role,
        language=employee.language,
        pin=pin,
        email=employee.email,
        password=password,
    )


@router.patch("/staff/{employee_id}", response_model=EmployeeOut)
async def update_staff(
    venue_id: int,
    employee_id: int,
    payload: StaffUpdateRequest,
    current: CurrentEmployee = Depends(require_manager),
    db: AsyncSession = Depends(get_session),
) -> EmployeeOut:
    """Поправить сотрудника: имя, кличку, роль, язык, активность.

    Смена роли меняет и группы связи — иначе человек, переведённый из зала на
    кухню, продолжал бы слышать зал и не слышать кухню.
    """
    require_own_venue(current, venue_id)

    employee = await db.get(Employee, employee_id)
    if (
        employee is None
        or employee.venue_id != venue_id
        or employee.deleted_at is not None
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")

    if payload.role is not None:
        if payload.role not in EMPLOYEE_ROLES:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Неизвестная роль. Допустимо: {', '.join(EMPLOYEE_ROLES)}",
            )
        if payload.role != employee.role:
            # Пересобираем группы под новую роль: старые связки убираем, иначе
            # человек остался бы слышать прежний цех.
            старые = (
                await db.execute(
                    select(EmployeeCommGroup).where(
                        EmployeeCommGroup.employee_id == employee.id
                    )
                )
            ).scalars().all()
            for связка in старые:
                await db.delete(связка)

            группы = (
                await db.execute(
                    select(CommGroup.id, CommGroup.name).where(
                        CommGroup.venue_id == venue_id, CommGroup.deleted_at.is_(None)
                    )
                )
            ).all()
            по_имени = {имя: gid for gid, имя in группы}
            for group in ROLE_GROUPS[payload.role]:
                gid = по_имени.get(group.value)
                if gid is not None:
                    db.add(
                        EmployeeCommGroup(employee_id=employee.id, comm_group_id=gid)
                    )
        employee.role = payload.role

    if payload.language is not None:
        if payload.language not in LANGUAGES:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Неизвестный язык. Допустимо: {', '.join(LANGUAGES)}",
            )
        employee.language = payload.language

    if payload.nickname is not None:
        новая = payload.nickname.strip() or None
        if новая:
            чужие = (
                await db.execute(
                    select(Employee.nickname).where(
                        Employee.venue_id == venue_id,
                        Employee.id != employee.id,
                        Employee.deleted_at.is_(None),
                        Employee.nickname.isnot(None),
                    )
                )
            ).scalars().all()
            проблемы = check_nicknames(
                [*чужие, новая], menu_names=await _venue_menu_words(db, venue_id)
            )
            своя = [p for p in проблемы if p.nickname == новая]
            if своя:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(своя[0])
                )
        employee.nickname = новая

    if payload.name is not None:
        employee.name = payload.name.strip()

    if payload.is_active is not None:
        employee.is_active = payload.is_active

    await db.commit()
    await db.refresh(employee)

    return EmployeeOut(
        id=employee.id,
        name=employee.name,
        nickname=employee.nickname,
        role=employee.role,
        language=employee.language,
        is_active=employee.is_active,
        hired_at=employee.hired_at,
    )
