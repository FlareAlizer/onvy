"""Вход по PIN, обновление токена, одноразовый тикет для WebSocket.

- GET  /api/auth/venues/{venue_id}/employees — список сотрудников точки для
  экрана входа (сотрудник выбирает себя по имени, затем вводит PIN).
- POST /api/auth/login   — PIN → пара JWT (access + refresh).
- POST /api/auth/refresh — ротация refresh-токена → новая пара.
- POST /api/auth/ws-ticket — аутентифицированный клиент получает одноразовый
  тикет для последующего подключения к WS без ключа в query-строке.

Ничего из внутреннего состояния (существует ли сотрудник, почему именно отказ)
наружу не течёт: и "сотрудника нет", и "PIN неверный" отвечают одной и той же
фразой с одним и тем же кодом 401 — иначе форма логина превращается в оракул
для перебора сотрудников (см. app/services/auth.py verify_pin).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.db.models.employee import Employee
from app.db.models.venue import Venue
from app.deps import CurrentEmployee, get_redis, require_employee
from app.schemas.auth import (
    EmailLoginRequest,
    EmployeeLoginOption,
    LoginRequest,
    MeOut,
    RefreshRequest,
    TokenPair,
    WsTicketOut,
)
from app.services import auth as auth_service
from app.services.rate_limit import RateLimitRule, rate_limit_dependency

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# Вход подбором PIN — главная угроза короткого PIN-кода (spec §6). Лимит по IP
# ловит распределённый перебор по разным employee_id с одного устройства/сети;
# блокировку по конкретному сотруднику после N попыток даёт auth_service
# (register_failed_pin_attempt/check_not_locked_out) отдельно.
_LOGIN_RATE_LIMIT = RateLimitRule(limit=20, window_seconds=60)
_login_rate_limited = rate_limit_dependency(_LOGIN_RATE_LIMIT, key_prefix="login")


def _invalid_credentials() -> HTTPException:
    """Один и тот же отказ для обоих способов входа.

    Формулировка намеренно не уточняет, что именно не сошлось: разные тексты
    для «нет такого» и «пароль не тот» превращают форму входа в способ узнать,
    кто здесь работает.
    """
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Данные для входа не подходят",
    )


@router.get("/venues/{venue_id}/employees", response_model=list[EmployeeLoginOption])
async def list_login_options(
    venue_id: int, db: AsyncSession = Depends(get_session)
) -> list[Employee]:
    """Публичный список активных сотрудников точки — для выбора себя на экране входа.

    Отдаёт только id/имя/роль/язык. Никогда pin_hash, никогда неактивных/уволенных.
    """
    rows = (
        await db.execute(
            select(Employee).where(
                Employee.venue_id == venue_id,
                Employee.is_active.is_(True),
                Employee.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    return list(rows)


@router.post("/login", response_model=TokenPair, dependencies=[Depends(_login_rate_limited)])
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> TokenPair:
    """PIN-вход. Блокируется после settings.pin_max_attempts неудач подряд."""
    try:
        await auth_service.check_not_locked_out(redis, payload.employee_id)
    except auth_service.AccountLockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком много неверных попыток, попробуйте позже",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc

    employee = await db.get(Employee, payload.employee_id)
    is_eligible = (
        employee is not None and employee.deleted_at is None and employee.is_active
    )
    pin_ok = auth_service.verify_pin(payload.pin, employee.pin_hash if is_eligible else None)

    if not is_eligible or not pin_ok:
        await auth_service.register_failed_pin_attempt(redis, payload.employee_id)
        raise _invalid_credentials()

    await auth_service.clear_pin_attempts(redis, employee.id)
    issued = await auth_service.issue_token_pair(
        redis, employee_id=employee.id, venue_id=employee.venue_id, role=employee.role
    )
    logger.info("Вход сотрудника %s (точка %s)", employee.id, employee.venue_id)
    return TokenPair(
        access_token=issued.access_token,
        refresh_token=issued.refresh_token,
        expires_in=issued.expires_in,
    )


@router.post(
    "/login-email", response_model=TokenPair, dependencies=[Depends(_login_rate_limited)]
)
async def login_email(
    payload: EmailLoginRequest,
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> TokenPair:
    """Вход по почте и паролю — основной способ.

    Отказ всегда один и тот же: клиент не должен по ответу отличать «такой почты
    нет» от «пароль неверный», иначе форма входа превращается в способ узнать,
    кто у нас работает. По той же причине проверка пароля выполняется всегда,
    даже когда сотрудник не найден — иначе разница во времени ответа выдаст
    существующие адреса.
    """
    email = auth_service.normalize_email(payload.email)

    employee = (
        await db.execute(
            select(Employee).where(
                Employee.email == email,
                Employee.is_active.is_(True),
                Employee.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    if employee is not None:
        try:
            await auth_service.check_not_locked_out(redis, employee.id)
        except auth_service.AccountLockedError as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Слишком много неверных попыток, попробуйте позже",
                headers={"Retry-After": str(exc.retry_after_seconds)},
            ) from exc

    password_ok = auth_service.verify_password(
        payload.password, employee.password_hash if employee is not None else None
    )

    if employee is None or not password_ok:
        if employee is not None:
            await auth_service.register_failed_pin_attempt(redis, employee.id)
        raise _invalid_credentials()

    await auth_service.clear_pin_attempts(redis, employee.id)
    issued = await auth_service.issue_token_pair(
        redis, employee_id=employee.id, venue_id=employee.venue_id, role=employee.role
    )
    logger.info("Вход по почте: сотрудник %s (точка %s)", employee.id, employee.venue_id)
    return TokenPair(
        access_token=issued.access_token,
        refresh_token=issued.refresh_token,
        expires_in=issued.expires_in,
    )


@router.get("/me", response_model=MeOut)
async def me(
    current: CurrentEmployee = Depends(require_employee),
    db: AsyncSession = Depends(get_session),
) -> MeOut:
    """Кто вошёл. Клиент по этому решает, какой кабинет показывать."""
    employee = await db.get(Employee, current.id)
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Сотрудник не найден"
        )
    venue = await db.get(Venue, employee.venue_id)
    return MeOut(
        id=employee.id,
        venue_id=employee.venue_id,
        venue_name=venue.name if venue else "",
        name=employee.name,
        nickname=employee.nickname,
        email=employee.email,
        role=employee.role,
        language=employee.language,
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> TokenPair:
    """Обновление пары токенов.

    Повтор того же запроса в пределах короткого окна (клиент не получил ответ,
    потому что моргнула сеть) возвращает ту же пару — это норма мобильной сети,
    а не атака. Предъявление давно использованного токена — уже компрометация:
    гасим все сессии сотрудника и требуем нового входа.
    """
    try:
        token_payload = auth_service.decode_token(payload.refresh_token, expected_type="refresh")
    except auth_service.TokenExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Токен просрочен"
        ) from exc
    except auth_service.TokenInvalidError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный токен"
        ) from exc

    try:
        await auth_service.verify_epoch_current(redis, token_payload)
    except auth_service.TokenRevokedError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Токен отозван"
        ) from exc

    assert token_payload.jti is not None  # decode_token гарантирует jti для refresh

    employee = await db.get(Employee, token_payload.employee_id)
    if employee is None or employee.deleted_at is not None or not employee.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Сотрудник неактивен"
        )

    outcome = await auth_service.rotate_refresh_token(
        redis,
        employee_id=employee.id,
        venue_id=employee.venue_id,
        role=employee.role,
        jti=token_payload.jti,
    )

    if outcome.status == "replayed":
        # Клиент не получил наш прошлый ответ (сеть моргнула) и повторил запрос.
        # Отдаём ту же пару: это не атака, и выкидывать человека из смены не за что.
        logger.info(
            "Повтор обновления токена сотрудника %s в пределах окна — отдаю ту же пару",
            employee.id,
        )
        assert outcome.tokens is not None
        return TokenPair(
            access_token=outcome.tokens.access_token,
            refresh_token=outcome.tokens.refresh_token,
            expires_in=outcome.tokens.expires_in,
        )

    if outcome.status == "reuse":
        # Токен использован давно — окно повтора уже закрылось. Значит это не
        # потерянный ответ, а чужая копия токена. Гасим все сессии сотрудника.
        await auth_service.bump_token_epoch(redis, token_payload.employee_id)
        logger.warning(
            "Повторное предъявление refresh-токена сотрудника %s — все сессии отозваны",
            token_payload.employee_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен уже был использован, войдите заново",
        )

    assert outcome.tokens is not None  # status == "rotated"
    return TokenPair(
        access_token=outcome.tokens.access_token,
        refresh_token=outcome.tokens.refresh_token,
        expires_in=outcome.tokens.expires_in,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshRequest, redis: Redis = Depends(get_redis)) -> None:
    """Выйти из аккаунта: погасить refresh-токен этого устройства.

    Без этого «выход» стирал только память браузера, а refresh-токен оставался
    рабочим ещё тридцать суток. На телефоне, который переходит следующей смене,
    это не выход, а видимость выхода.

    Гасим именно предъявленный токен, а не все сессии сотрудника: управляющий
    сидит и в зале с телефона, и в кабинете с компьютера, и выход на одном не
    должен выбрасывать его со второго. Access-токен доживает свои полчаса сам —
    отзывать его нечем, но из браузера он уже стёрт.

    Ответ всегда 204, даже если токен просрочен, подделан или уже погашен:
    выход не имеет права не сработать, иначе человек остаётся в аккаунте
    с сообщением об ошибке и без способа выйти.
    """
    try:
        token = auth_service.decode_token(payload.refresh_token, expected_type="refresh")
    except (auth_service.TokenExpiredError, auth_service.TokenInvalidError):
        return

    if token.jti is not None:
        await auth_service.consume_refresh_jti(redis, token.employee_id, token.jti)
        logger.info("Сотрудник %s вышел из аккаунта", token.employee_id)


@router.post("/ws-ticket", response_model=WsTicketOut)
async def issue_ws_ticket(
    current: CurrentEmployee = Depends(require_employee),
    redis: Redis = Depends(get_redis),
) -> WsTicketOut:
    """Одноразовый короткоживущий тикет для подключения к WS без ключа в URL.

    Точка интеграции для app/api/comms.py (переписывается в лупе связи):
    клиент вызывает этот эндпоинт с обычным access-токеном (заголовок
    Authorization), получает ticket, затем открывает
    `GET /ws/comms/{employee_id}?ticket=...`. Обработчик WS вместо сравнения
    query-параметра с settings.api_key должен вызвать
    `app.services.auth.consume_ws_ticket(redis, ticket)` — None означает
    неизвестный/просроченный/уже использованный тикет (закрыть сокет с
    WS_1008_POLICY_VIOLATION), иначе сверить employee_id из тикета с
    employee_id из пути/сообщения перед `manager.connect(...)`.
    """
    ticket = await auth_service.issue_ws_ticket(
        redis, employee_id=current.id, venue_id=current.venue_id, role=current.role
    )
    return WsTicketOut(ticket=ticket, expires_in=auth_service.WS_TICKET_TTL_SECONDS)
