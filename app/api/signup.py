"""Регистрация заведения вместе с управляющим.

Одна форма вместо мастера: название заведения, имя, почта, пароль. Всё, что
нужно для работы — группы связи, роль, привязка к точке — создаётся здесь же,
чтобы человек после регистрации сразу попал в рабочий кабинет, а не в пустой
экран с просьбой что-то настроить.

Регистрация создаёт ТОЛЬКО новое заведение. Присоединиться к существующему
самостоятельно нельзя: иначе любой, кто знает название чайханы, завёл бы себе
там доступ. Сотрудников добавляет управляющий.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.db.models.comm_group import CommGroup, EmployeeCommGroup
from app.db.models.employee import Employee
from app.db.models.venue import Venue
from app.db.seed import ROLE_GROUPS, generate_unique_pins
from app.deps import get_redis
from app.domain.intents import Group
from app.schemas.signup import VenueSignupRequest, VenueSignupResult
from app.services import auth as auth_service
from app.services.rate_limit import RateLimitRule, rate_limit_dependency

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/signup", tags=["signup"])

# Регистрация — дорогая операция (создаёт заведение) и удобная мишень для
# спама. Пять в час с адреса: живому человеку хватает с запасом.
_signup_rate_limited = rate_limit_dependency(
    RateLimitRule(limit=5, window_seconds=3600), key_prefix="signup"
)


@router.post(
    "/venue",
    response_model=VenueSignupResult,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_signup_rate_limited)],
)
async def signup_venue(
    payload: VenueSignupRequest,
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> VenueSignupResult:
    """Завести заведение и управляющего в нём."""
    email = auth_service.normalize_email(payload.email)

    занято = (
        await db.execute(
            select(Employee.id).where(
                Employee.email == email, Employee.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if занято is not None:
        # Здесь, в отличие от формы входа, сказать прямо можно и нужно: человек
        # регистрируется и должен понять, что у него уже есть доступ.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Эта почта уже занята — попробуйте войти",
        )

    название = payload.venue_name.strip()
    # Сравниваем в Python, а не через SQL lower(): на SQLite он ASCII-only и
    # кириллицу не сворачивает вовсе, а на Postgres результат зависит от локали
    # сервера. Заведений десятки, выборка дешёвая — надёжность важнее.
    занятые_названия = (
        (await db.execute(select(Venue.name).where(Venue.deleted_at.is_(None))))
        .scalars()
        .all()
    )
    if any(имя.casefold() == название.casefold() for имя in занятые_названия):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Заведение с таким названием уже зарегистрировано. "
                "Если это ваше — попросите управляющего добавить вас в команду."
            ),
        )

    venue = Venue(
        name=название,
        timezone=payload.timezone.strip() or "Europe/Moscow",
        default_language=payload.default_language,
    )
    db.add(venue)
    await db.flush()

    # Группы связи создаются сразу: без них рация не заработает, а требовать
    # от человека «настроить группы» после регистрации — лишний шаг, который
    # он всё равно не поймёт.
    группы: dict[Group, CommGroup] = {}
    for group in Group:
        cg = CommGroup(venue_id=venue.id, name=group.value)
        db.add(cg)
        группы[group] = cg
    await db.flush()

    # PIN нужен даже управляющему: он тоже выходит в зал, а там почта неудобна.
    pin = generate_unique_pins(1)[0]
    manager = Employee(
        venue_id=venue.id,
        name=payload.manager_name.strip(),
        role="manager",
        language=payload.default_language,
        email=email,
        password_hash=auth_service.hash_password(payload.password),
        pin_hash=auth_service.hash_pin(pin),
    )
    db.add(manager)
    await db.flush()

    for group in ROLE_GROUPS["manager"]:
        db.add(
            EmployeeCommGroup(employee_id=manager.id, comm_group_id=группы[group].id)
        )

    await db.commit()

    issued = await auth_service.issue_token_pair(
        redis, employee_id=manager.id, venue_id=venue.id, role="manager"
    )
    logger.info(
        "Зарегистрировано заведение %s (id=%s), управляющий %s",
        venue.name,
        venue.id,
        manager.id,
    )

    return VenueSignupResult(
        venue_id=venue.id,
        venue_name=venue.name,
        employee_id=manager.id,
        access_token=issued.access_token,
        refresh_token=issued.refresh_token,
        expires_in=issued.expires_in,
    )
