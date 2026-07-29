"""Ядро аутентификации: PIN-хеширование, JWT, отзыв токенов, блокировка входа,
одноразовые тикеты для WebSocket.

Ничего здесь не трогает БД напрямую (сессия — забота обработчика в app/api/auth.py);
модуль работает с уже загруженным сотрудником и с Redis-клиентом, которые ему передают.

Модель отзыва токенов — версия («эпоха») на сотрудника в Redis, не список отозванных
jti: увольнение/блокировка сотрудника обязаны обесценить его access- и refresh-токены
немедленно (specs/pilot-chaihana.md §6), а не только по истечении access-токена.
Каждый выданный токен несёт эпоху на момент выдачи; bump_token_epoch увеличивает
счётчик — все токены с прежней эпохой перестают проходить проверку сразу.

Refresh-токены дополнительно ротируются: у каждого свой jti, одноразовый в Redis.
Повторное предъявление уже использованного refresh — сигнал компрометации:
эпоха сотрудника поднимается, все его сессии (включая ещё не истёкшие access-токены
у других устройств) гасятся.
"""

from __future__ import annotations

import json
import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Literal

import jwt
from argon2 import PasswordHasher
from argon2 import exceptions as argon2_exceptions
from redis.asyncio import Redis

from app.config import settings

JWT_ALGORITHM = "HS256"
TokenType = Literal["access", "refresh"]

# Тикет для входящего WS-подключения: одноразовый и короткоживущий (30-60 с из
# спеки §6). Не вынесено в settings — это деталь протокола хендшейка, а не
# параметр, который управляющий должен крутить в конфиге.
WS_TICKET_TTL_SECONDS = 45

_password_hasher = PasswordHasher()
# Фиктивный хеш для сравнения времени, когда сотрудника с таким id не существует —
# иначе разница во времени ответа выдаёт перебором список существующих id
# (см. требование "не отдавать наружу, существует ли сотрудник").
_DUMMY_PIN_HASH = _password_hasher.hash(secrets.token_hex(8))


class AuthError(Exception):
    """Базовая ошибка аутентификации/авторизации домена."""


class InvalidCredentialsError(AuthError):
    """Неверный сотрудник или PIN. Намеренно не различаются на границе API."""


class AccountLockedError(AuthError):
    """Слишком много неверных попыток PIN подряд — временная блокировка входа."""

    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__("Вход временно заблокирован")


class TokenInvalidError(AuthError):
    """Токен повреждён, не того типа или подпись не сходится."""


class TokenExpiredError(AuthError):
    """Токен просрочен."""


class TokenRevokedError(AuthError):
    """Токен отозван (сменилась эпоха сотрудника — увольнение/принудительный логаут)."""


# --- PIN -----------------------------------------------------------------------


def hash_pin(pin: str) -> str:
    """Хешировать PIN для хранения (argon2id)."""
    return _password_hasher.hash(pin)


def verify_pin(pin: str, pin_hash: str | None) -> bool:
    """Сверить PIN с хешем. pin_hash=None (сотрудник не найден) — фиктивная сверка.

    Всегда выполняет argon2-проверку (на реальном или фиктивном хеше), чтобы не
    палить наличие сотрудника разницей во времени ответа.
    """
    try:
        _password_hasher.verify(pin_hash or _DUMMY_PIN_HASH, pin)
    except (argon2_exceptions.VerifyMismatchError, argon2_exceptions.VerificationError,
             argon2_exceptions.InvalidHashError):
        return False
    return pin_hash is not None


# --- Блокировка после N неудачных попыток (Redis) -------------------------------

_ATTEMPTS_KEY = "auth:pin_attempts:{employee_id}"


async def register_failed_pin_attempt(redis: Redis, employee_id: int) -> None:
    """Учесть неудачную попытку. Окно блокировки открывается с первой неудачи подряд."""
    key = _ATTEMPTS_KEY.format(employee_id=employee_id)
    attempts = await redis.incr(key)
    if attempts == 1:
        await redis.expire(key, settings.pin_lockout_minutes * 60)


async def clear_pin_attempts(redis: Redis, employee_id: int) -> None:
    """Сбросить счётчик после успешного входа."""
    await redis.delete(_ATTEMPTS_KEY.format(employee_id=employee_id))


async def check_not_locked_out(redis: Redis, employee_id: int) -> None:
    """Поднять AccountLockedError, если попыток уже settings.pin_max_attempts и больше."""
    key = _ATTEMPTS_KEY.format(employee_id=employee_id)
    raw = await redis.get(key)
    attempts = int(raw) if raw is not None else 0
    if attempts >= settings.pin_max_attempts:
        ttl = await redis.ttl(key)
        raise AccountLockedError(retry_after_seconds=max(ttl, 1))


# --- Эпоха токенов сотрудника (отзыв) -------------------------------------------

_EPOCH_KEY = "auth:token_epoch:{employee_id}"


async def get_token_epoch(redis: Redis, employee_id: int) -> int:
    raw = await redis.get(_EPOCH_KEY.format(employee_id=employee_id))
    return int(raw) if raw is not None else 0


async def bump_token_epoch(redis: Redis, employee_id: int) -> int:
    """Отозвать разом все выданные токены сотрудника (увольнение, logout-all, реюз refresh)."""
    return await redis.incr(_EPOCH_KEY.format(employee_id=employee_id))


# --- JWT -------------------------------------------------------------------------


@dataclass(frozen=True)
class TokenPayload:
    employee_id: int
    venue_id: int
    role: str
    token_type: TokenType
    epoch: int
    jti: str | None = None


def _encode(payload: dict, ttl_seconds: int) -> str:
    now = int(time.time())
    claims = {**payload, "iat": now, "exp": now + ttl_seconds}
    return jwt.encode(claims, settings.secret_key, algorithm=JWT_ALGORITHM)


def create_access_token(*, employee_id: int, venue_id: int, role: str, epoch: int) -> str:
    return _encode(
        {
            "sub": str(employee_id),
            "venue_id": venue_id,
            "role": role,
            "type": "access",
            "epoch": epoch,
        },
        ttl_seconds=settings.access_token_ttl_minutes * 60,
    )


def create_refresh_token(
    *, employee_id: int, venue_id: int, role: str, epoch: int
) -> tuple[str, str]:
    """Вернуть (токен, jti) — jti нужен вызывающему коду, чтобы сохранить его в Redis."""
    jti = uuid.uuid4().hex
    token = _encode(
        {
            "sub": str(employee_id),
            "venue_id": venue_id,
            "role": role,
            "type": "refresh",
            "epoch": epoch,
            "jti": jti,
        },
        ttl_seconds=settings.refresh_token_ttl_days * 86400,
    )
    return token, jti


def decode_token(token: str, expected_type: TokenType) -> TokenPayload:
    """Проверить подпись/срок и тип токена. Не проверяет эпоху — это отдельный шаг
    (требует Redis, а декодирование — чистая операция)."""
    try:
        claims = jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("Токен просрочен") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenInvalidError("Токен повреждён или недействителен") from exc

    if claims.get("type") != expected_type:
        raise TokenInvalidError(f"Ожидался токен типа {expected_type!r}")

    try:
        employee_id = int(claims["sub"])
        venue_id = int(claims["venue_id"])
        role = str(claims["role"])
        epoch = int(claims["epoch"])
    except (KeyError, ValueError, TypeError) as exc:
        raise TokenInvalidError("Токен не содержит обязательных полей") from exc

    jti = claims.get("jti")
    if expected_type == "refresh" and not jti:
        raise TokenInvalidError("Refresh-токен без jti")

    return TokenPayload(
        employee_id=employee_id,
        venue_id=venue_id,
        role=role,
        token_type=expected_type,
        epoch=epoch,
        jti=jti,
    )


async def verify_epoch_current(redis: Redis, payload: TokenPayload) -> None:
    """Поднять TokenRevokedError, если токен выдан в уже отозванной эпохе."""
    current = await get_token_epoch(redis, payload.employee_id)
    if payload.epoch != current:
        raise TokenRevokedError("Токен отозван")


# --- Ротация refresh-токенов (одноразовый jti в Redis) --------------------------

_REFRESH_JTI_KEY = "auth:refresh_jti:{employee_id}:{jti}"


async def store_refresh_jti(redis: Redis, employee_id: int, jti: str) -> None:
    key = _REFRESH_JTI_KEY.format(employee_id=employee_id, jti=jti)
    await redis.set(key, "1", ex=settings.refresh_token_ttl_days * 86400)


async def consume_refresh_jti(redis: Redis, employee_id: int, jti: str) -> bool:
    """Списать jti как использованный. True, если он был валиден (первое предъявление)."""
    key = _REFRESH_JTI_KEY.format(employee_id=employee_id, jti=jti)
    deleted = await redis.delete(key)
    return deleted == 1


# --- Повтор обновления токена ----------------------------------------------------

# Сколько секунд после успешного обновления мы отвечаем на повтор той же парой
# вместо того, чтобы считать это компрометацией.
#
# Зачем это нужно. Телефон официанта в зале теряет сеть постоянно. Обычный
# сценарий: клиент отправил refresh, сервер обновил токены, ответ не доехал.
# Клиент повторяет запрос со старым токеном — и без этого окна получает
# «все сессии отозваны» и вылетает на экран входа посреди смены.
# Это не атака, это мобильная сеть.
#
# Безопасность при этом остаётся: украденный токен, предъявленный позже окна,
# по-прежнему гасит все сессии сотрудника и требует нового входа.
REFRESH_REPLAY_GRACE_SECONDS = 30

_REFRESH_REPLAY_KEY = "auth:refresh_replay:{employee_id}:{jti}"


@dataclass(frozen=True)
class RefreshOutcome:
    """Чем закончилась попытка обновить пару токенов."""

    # rotated — обычное обновление; replayed — повтор в пределах окна;
    # reuse — предъявлен давно использованный токен, это компрометация.
    status: Literal["rotated", "replayed", "reuse"]
    tokens: IssuedTokens | None = None


async def rotate_refresh_token(
    redis: Redis, *, employee_id: int, venue_id: int, role: str, jti: str
) -> RefreshOutcome:
    """Обновить пару токенов, переживая повтор запроса из-за потери сети."""
    if await consume_refresh_jti(redis, employee_id, jti):
        tokens = await issue_token_pair(
            redis, employee_id=employee_id, venue_id=venue_id, role=role
        )
        # Запоминаем выданную пару на короткое время: если клиент не получил
        # ответ и повторит запрос, он получит ровно то же самое.
        await redis.set(
            _REFRESH_REPLAY_KEY.format(employee_id=employee_id, jti=jti),
            json.dumps(
                {
                    "access_token": tokens.access_token,
                    "refresh_token": tokens.refresh_token,
                    "expires_in": tokens.expires_in,
                }
            ),
            ex=REFRESH_REPLAY_GRACE_SECONDS,
        )
        return RefreshOutcome(status="rotated", tokens=tokens)

    stored = await redis.get(_REFRESH_REPLAY_KEY.format(employee_id=employee_id, jti=jti))
    if stored:
        data = json.loads(stored)
        return RefreshOutcome(
            status="replayed",
            tokens=IssuedTokens(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                expires_in=data["expires_in"],
            ),
        )

    return RefreshOutcome(status="reuse")


@dataclass(frozen=True)
class IssuedTokens:
    """Пара токенов, как её отдаёт сервис. app/api/auth.py оборачивает в TokenPair-схему."""

    access_token: str
    refresh_token: str
    expires_in: int


async def issue_token_pair(
    redis: Redis, *, employee_id: int, venue_id: int, role: str
) -> IssuedTokens:
    """Выдать новую пару токенов текущей эпохи и зарегистрировать refresh jti."""
    epoch = await get_token_epoch(redis, employee_id)
    access = create_access_token(
        employee_id=employee_id, venue_id=venue_id, role=role, epoch=epoch
    )
    refresh, jti = create_refresh_token(
        employee_id=employee_id, venue_id=venue_id, role=role, epoch=epoch
    )
    await store_refresh_jti(redis, employee_id, jti)
    return IssuedTokens(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_ttl_minutes * 60,
    )


# --- Одноразовый WS-тикет --------------------------------------------------------

_WS_TICKET_KEY = "auth:ws_ticket:{ticket}"


@dataclass(frozen=True)
class WsTicketData:
    employee_id: int
    venue_id: int
    role: str


async def issue_ws_ticket(redis: Redis, *, employee_id: int, venue_id: int, role: str) -> str:
    """Выпустить одноразовый тикет для последующего WS-подключения без ключа в URL."""
    ticket = secrets.token_urlsafe(32)
    value = f"{employee_id}:{venue_id}:{role}"
    await redis.set(_WS_TICKET_KEY.format(ticket=ticket), value, ex=WS_TICKET_TTL_SECONDS)
    return ticket


async def consume_ws_ticket(redis: Redis, ticket: str) -> WsTicketData | None:
    """Погасить тикет атомарно и вернуть его содержимое.

    None — тикет неизвестен, просрочен или уже был использован.

    Точка интеграции для обработчика WebSocket (app/api/comms.py, переписывается
    в лупе связи): вместо `?api_key=...` в query — `?ticket=...`, и он вызывает
    именно эту функцию вместо сравнения с settings.api_key.
    """
    key = _WS_TICKET_KEY.format(ticket=ticket)
    raw = await redis.getdel(key)
    if raw is None:
        return None
    try:
        employee_id_s, venue_id_s, role = raw.split(":", 2)
        return WsTicketData(employee_id=int(employee_id_s), venue_id=int(venue_id_s), role=role)
    except ValueError:
        return None
