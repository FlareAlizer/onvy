"""Общие зависимости FastAPI: аутентификация, авторизация по ролям, Redis.

Общий API-ключ на всех сотрудников, который был здесь в демо, удалён вместе с
ритейл-роутерами: он давал любому доступ ко всем разговорам и светился в URL
вебсокета. Теперь вход только по PIN и JWT (app/services/auth.py).
"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis, from_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.db.models.employee import Employee
from app.services import auth as auth_service

# --- Redis -----------------------------------------------------------------------

_redis_client: Redis | None = None


def get_redis_client() -> Redis:
    """Единый клиент на процесс (redis-py сам держит пул соединений)."""
    global _redis_client
    if _redis_client is None:
        _redis_client = from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def get_redis() -> AsyncGenerator[Redis, None]:
    """Зависимость FastAPI: клиент Redis для блокировок, эпох токенов, тикетов, rate-limit."""
    yield get_redis_client()


# --- Аутентификация по JWT --------------------------------------------------------

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentEmployee:
    """Аутентифицированный сотрудник — то, что видит обработчик после require_employee."""

    id: int
    venue_id: int
    role: str
    language: str


async def require_employee(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_session),
) -> CurrentEmployee:
    """Проверить access-токен и вернуть текущего сотрудника.

    Два независимых уровня отзыва:
    1. Эпоха в Redis — увольнение/принудительный logout гасят токен мгновенно,
       не дожидаясь его естественного истечения (до 30 минут по умолчанию).
    2. Свежая проверка is_active/soft-delete в БД — на случай, если вызывающий
       код отключил сотрудника, не подумав вызвать bump_token_epoch явно.
    Оба сделаны намеренно избыточными: пилот с реальными людьми не может
    полагаться на то, что каждый будущий loop не забудет один из механизмов.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется Bearer-токен",
        )

    try:
        payload = auth_service.decode_token(credentials.credentials, expected_type="access")
        await auth_service.verify_epoch_current(redis, payload)
    except auth_service.TokenExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Токен просрочен"
        ) from exc
    except auth_service.TokenRevokedError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Токен отозван"
        ) from exc
    except auth_service.TokenInvalidError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный токен"
        ) from exc

    employee = await db.get(Employee, payload.employee_id)
    if employee is None or employee.deleted_at is not None or not employee.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Сотрудник неактивен"
        )

    return CurrentEmployee(
        id=employee.id,
        venue_id=employee.venue_id,
        role=employee.role,
        language=employee.language,
    )


async def require_manager(
    current: CurrentEmployee = Depends(require_employee),
) -> CurrentEmployee:
    """Требует роль manager. Проверка venue_id для конкретных ресурсов — на сервисе-вызывающем."""
    if current.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права управляющего",
        )
    return current
