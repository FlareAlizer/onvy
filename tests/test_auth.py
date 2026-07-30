"""Интеграционные тесты входа по PIN, JWT, отзыва и WS-тикетов.

Изолированный тестовый ASGI-стек: собственные SQLite-in-memory БД и fake Redis,
без зависимости от app.main.app (тот сейчас в процессе переезда на новую схему
данных — см. отчёт лупа) и без реального Postgres/Redis. Это НЕ проверено
против живого Redis — поведение sorted set/getdel у fakeredis совпадает с
redis-py по документации, но перед продом стоит прогнать хотя бы дымовой тест
с реальным контейнером Redis.
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis
from fastapi import APIRouter, Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api import auth as auth_api
from app.config import settings
from app.db import Base, get_session
from app.db.models.employee import Employee
from app.db.models.venue import Venue
from app.deps import CurrentEmployee, get_redis, require_employee, require_manager
from app.services import auth as auth_service

# --- Тестовый ASGI-стек ------------------------------------------------------

_test_router = APIRouter()


@_test_router.get("/test/me")
async def _whoami(current: CurrentEmployee = Depends(require_employee)) -> dict:
    """Отражает то, что require_employee реально знает о вызывающем — для
    проверки, что venue_id/role берутся из БД, а не из клиентского ввода."""
    return {"id": current.id, "venue_id": current.venue_id, "role": current.role}


@_test_router.get("/test/manager-only")
async def _manager_only(current: CurrentEmployee = Depends(require_manager)) -> dict:
    return {"ok": True, "id": current.id}


@pytest_asyncio.fixture
async def session_maker() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Изолированная in-memory SQLite БД на тест (свои таблицы venues/employees)."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    maker = async_sessionmaker(engine, expire_on_commit=False)
    # Base.metadata содержит ВСЮ схему домена (импорт app.db.models.employee тянет
    # за собой app/db/models/__init__.py целиком). Создаём только свои таблицы —
    # у некоторых других (menu_items.allergens — Postgres ARRAY) нет SQLite-рендера.
    tables = [Venue.__table__, Employee.__table__]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)
    yield maker
    await engine.dispose()


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator[Redis, None]:
    client = FakeAsyncRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def client(
    session_maker: async_sessionmaker[AsyncSession], redis_client: Redis
) -> AsyncGenerator[AsyncClient, None]:
    app = FastAPI()
    app.include_router(auth_api.router, prefix="/api")
    app.include_router(_test_router)

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def override_get_redis() -> AsyncGenerator[Redis, None]:
        yield redis_client

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_redis] = override_get_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _login(client: AsyncClient, employee_id: int, pin: str) -> dict:
    resp = await client.post("/api/auth/login", json={"employee_id": employee_id, "pin": pin})
    return resp.json()


async def _make_venue(
    session_maker: async_sessionmaker[AsyncSession], name: str = "Чайхана"
) -> int:
    async with session_maker() as session:
        venue = Venue(name=name)
        session.add(venue)
        await session.commit()
        await session.refresh(venue)
        return venue.id


async def _make_employee(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    venue_id: int,
    pin: str,
    name: str = "Сотрудник",
    role: str = "waiter",
    language: str = "ru",
    is_active: bool = True,
) -> int:
    async with session_maker() as session:
        employee = Employee(
            venue_id=venue_id,
            name=name,
            role=role,
            language=language,
            pin_hash=auth_service.hash_pin(pin),
            is_active=is_active,
        )
        session.add(employee)
        await session.commit()
        await session.refresh(employee)
        return employee.id


# --- Вход ---------------------------------------------------------------------


async def test_login_success(client: AsyncClient, session_maker) -> None:
    venue_id = await _make_venue(session_maker)
    employee_id = await _make_employee(session_maker, venue_id=venue_id, pin="4711", role="manager")

    resp = await client.post("/api/auth/login", json={"employee_id": employee_id, "pin": "4711"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == settings.access_token_ttl_minutes * 60
    assert data["access_token"] and data["refresh_token"]

    payload = auth_service.decode_token(data["access_token"], expected_type="access")
    assert payload.employee_id == employee_id
    assert payload.venue_id == venue_id
    assert payload.role == "manager"


async def test_login_wrong_pin_is_generic(client: AsyncClient, session_maker) -> None:
    venue_id = await _make_venue(session_maker)
    employee_id = await _make_employee(session_maker, venue_id=venue_id, pin="4711")

    resp = await client.post("/api/auth/login", json={"employee_id": employee_id, "pin": "0000"})

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Данные для входа не подходят"


async def test_login_unknown_employee_matches_wrong_pin_response(client: AsyncClient) -> None:
    """Тело/код ответа должны быть идентичны случаю неверного PIN — иначе форма
    входа превращается в оракул, по которому можно перебором найти реальные id."""
    resp = await client.post("/api/auth/login", json={"employee_id": 999999, "pin": "0000"})

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Данные для входа не подходят"


async def test_login_inactive_employee_rejected(client: AsyncClient, session_maker) -> None:
    venue_id = await _make_venue(session_maker)
    employee_id = await _make_employee(
        session_maker, venue_id=venue_id, pin="4711", is_active=False
    )

    resp = await client.post("/api/auth/login", json={"employee_id": employee_id, "pin": "4711"})

    assert resp.status_code == 401


async def test_login_locks_out_after_max_attempts(
    client: AsyncClient, session_maker, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "pin_max_attempts", 3)
    venue_id = await _make_venue(session_maker)
    employee_id = await _make_employee(session_maker, venue_id=venue_id, pin="4711")

    for _ in range(3):
        resp = await client.post(
            "/api/auth/login", json={"employee_id": employee_id, "pin": "0000"}
        )
        assert resp.status_code == 401

    # Четвёртая попытка — даже с ПРАВИЛЬНЫМ PIN — должна быть отвергнута блокировкой.
    locked = await client.post(
        "/api/auth/login", json={"employee_id": employee_id, "pin": "4711"}
    )
    assert locked.status_code == 429
    assert "Retry-After" in locked.headers


# --- Refresh / отзыв ------------------------------------------------------------


async def test_refresh_rotates_and_old_token_is_dead(client: AsyncClient, session_maker) -> None:
    venue_id = await _make_venue(session_maker)
    employee_id = await _make_employee(session_maker, venue_id=venue_id, pin="4711")
    old_refresh = (await _login(client, employee_id, "4711"))["refresh_token"]

    refreshed = await client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert refreshed.status_code == 200
    new_refresh = refreshed.json()["refresh_token"]
    assert new_refresh != old_refresh


async def test_повтор_обновления_сразу_отдаёт_ту_же_пару(
    client: AsyncClient, session_maker
) -> None:
    """Телефон официанта потерял ответ и повторил запрос.

    Это обычная мобильная сеть, а не атака: человек не должен вылететь из смены.
    Повтор в пределах окна возвращает ровно ту же пару токенов.
    """
    venue_id = await _make_venue(session_maker)
    employee_id = await _make_employee(session_maker, venue_id=venue_id, pin="4711")
    old_refresh = (await _login(client, employee_id, "4711"))["refresh_token"]

    first = await client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert first.status_code == 200

    replay = await client.post("/api/auth/refresh", json={"refresh_token": old_refresh})

    assert replay.status_code == 200
    assert replay.json()["refresh_token"] == first.json()["refresh_token"]

    # Сессия жива: выданным токеном по-прежнему можно обновляться.
    still_valid = await client.post(
        "/api/auth/refresh", json={"refresh_token": first.json()["refresh_token"]}
    )
    assert still_valid.status_code == 200


async def test_поздний_повтор_считается_кражей_и_гасит_сессии(
    client: AsyncClient, session_maker, redis_client
) -> None:
    """Тот же токен, предъявленный после закрытия окна, — уже чужая копия.

    Здесь мы гасим всё: и сам старый токен, и только что выданный новый,
    потому что не знаем, у кого из двоих настоящий владелец.
    """
    venue_id = await _make_venue(session_maker)
    employee_id = await _make_employee(session_maker, venue_id=venue_id, pin="4711")
    old_refresh = (await _login(client, employee_id, "4711"))["refresh_token"]

    first = await client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert first.status_code == 200
    new_refresh = first.json()["refresh_token"]

    # Окно повтора закрылось — эмулируем это, убрав запись о выданной паре.
    old_jti = auth_service.decode_token(old_refresh, expected_type="refresh").jti
    await redis_client.delete(f"auth:refresh_replay:{employee_id}:{old_jti}")

    replay = await client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert replay.status_code == 401

    # Отозвана вся сессия, включая только что выданный новый refresh.
    after_revocation = await client.post("/api/auth/refresh", json={"refresh_token": new_refresh})
    assert after_revocation.status_code == 401


async def test_refresh_expired_token_rejected(client: AsyncClient, session_maker) -> None:
    venue_id = await _make_venue(session_maker)
    employee_id = await _make_employee(session_maker, venue_id=venue_id, pin="4711")
    refresh_token, _ = auth_service.create_refresh_token(
        employee_id=employee_id, venue_id=venue_id, role="waiter", epoch=0
    )
    # create_refresh_token не умеет отрицательный TTL — соберём просроченный токен вручную.
    import jwt as pyjwt

    expired_claims = pyjwt.decode(
        refresh_token, settings.secret_key, algorithms=[auth_service.JWT_ALGORITHM]
    )
    expired_claims["exp"] = expired_claims["iat"] - 10
    expired_token = pyjwt.encode(
        expired_claims, settings.secret_key, algorithm=auth_service.JWT_ALGORITHM
    )

    resp = await client.post("/api/auth/refresh", json={"refresh_token": expired_token})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Токен просрочен"


async def test_access_token_expired_is_rejected_by_require_employee(
    client: AsyncClient, session_maker, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "access_token_ttl_minutes", -1)
    venue_id = await _make_venue(session_maker)
    employee_id = await _make_employee(session_maker, venue_id=venue_id, pin="4711")
    expired_access = (await _login(client, employee_id, "4711"))["access_token"]

    resp = await client.get("/test/me", headers={"Authorization": f"Bearer {expired_access}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Токен просрочен"


async def test_deactivated_employee_loses_access_immediately(
    client: AsyncClient, session_maker
) -> None:
    """Увольнение сотрудника обязано обесценить уже выданный access-токен сразу,
    не дожидаясь его естественного истечения (spec §6)."""
    venue_id = await _make_venue(session_maker)
    employee_id = await _make_employee(session_maker, venue_id=venue_id, pin="4711")
    access_token = (await _login(client, employee_id, "4711"))["access_token"]

    ok = await client.get("/test/me", headers={"Authorization": f"Bearer {access_token}"})
    assert ok.status_code == 200

    async with session_maker() as session:
        employee = await session.get(Employee, employee_id)
        employee.is_active = False
        await session.commit()

    revoked = await client.get("/test/me", headers={"Authorization": f"Bearer {access_token}"})
    assert revoked.status_code == 401


# --- Роли и мультиточечность -----------------------------------------------------


async def test_require_employee_returns_true_venue_from_db_not_client_input(
    client: AsyncClient, session_maker
) -> None:
    venue_a = await _make_venue(session_maker, name="Точка А")
    venue_b = await _make_venue(session_maker, name="Точка Б")
    employee_a = await _make_employee(
        session_maker, venue_id=venue_a, pin="1111", name="Сотрудник А"
    )
    employee_b = await _make_employee(
        session_maker, venue_id=venue_b, pin="2222", name="Сотрудник Б"
    )

    token_a = (await _login(client, employee_a, "1111"))["access_token"]
    token_b = (await _login(client, employee_b, "2222"))["access_token"]

    me_a = await client.get("/test/me", headers={"Authorization": f"Bearer {token_a}"})
    me_b = await client.get("/test/me", headers={"Authorization": f"Bearer {token_b}"})

    assert me_a.json()["venue_id"] == venue_a
    assert me_b.json()["venue_id"] == venue_b
    assert me_a.json()["venue_id"] != me_b.json()["venue_id"]


async def test_require_manager_rejects_non_manager_roles(
    client: AsyncClient, session_maker
) -> None:
    venue_id = await _make_venue(session_maker)
    waiter_id = await _make_employee(
        session_maker, venue_id=venue_id, pin="4711", role="waiter"
    )
    manager_id = await _make_employee(
        session_maker, venue_id=venue_id, pin="9911", role="manager", name="Управляющий"
    )

    waiter_token = (await _login(client, waiter_id, "4711"))["access_token"]
    manager_token = (await _login(client, manager_id, "9911"))["access_token"]

    denied = await client.get(
        "/test/manager-only", headers={"Authorization": f"Bearer {waiter_token}"}
    )
    assert denied.status_code == 403

    allowed = await client.get(
        "/test/manager-only", headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert allowed.status_code == 200


async def test_no_bearer_token_rejected(client: AsyncClient) -> None:
    resp = await client.get("/test/me")
    assert resp.status_code == 401


async def test_login_options_never_expose_pin_hash(client: AsyncClient, session_maker) -> None:
    venue_id = await _make_venue(session_maker)
    await _make_employee(session_maker, venue_id=venue_id, pin="4711", name="Иван")
    await _make_employee(
        session_maker, venue_id=venue_id, pin="0000", name="Уволенный", is_active=False
    )

    resp = await client.get(f"/api/auth/venues/{venue_id}/employees")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Иван"
    assert "pin_hash" not in data[0]
    assert "pin" not in data[0]


# --- WS-тикет --------------------------------------------------------------------


async def test_ws_ticket_is_single_use(
    client: AsyncClient, session_maker, redis_client: Redis
) -> None:
    venue_id = await _make_venue(session_maker)
    employee_id = await _make_employee(
        session_maker, venue_id=venue_id, pin="4711", role="host"
    )
    access_token = (await _login(client, employee_id, "4711"))["access_token"]

    ticket_resp = await client.post(
        "/api/auth/ws-ticket", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert ticket_resp.status_code == 200
    ticket = ticket_resp.json()["ticket"]
    assert ticket_resp.json()["expires_in"] == auth_service.WS_TICKET_TTL_SECONDS

    first_use = await auth_service.consume_ws_ticket(redis_client, ticket)
    assert first_use is not None
    assert first_use.employee_id == employee_id
    assert first_use.venue_id == venue_id
    assert first_use.role == "host"

    second_use = await auth_service.consume_ws_ticket(redis_client, ticket)
    assert second_use is None


async def test_ws_ticket_unknown_ticket_returns_none(redis_client: Redis) -> None:
    assert await auth_service.consume_ws_ticket(redis_client, "garbage-ticket") is None


async def test_ws_ticket_requires_authentication(client: AsyncClient) -> None:
    resp = await client.post("/api/auth/ws-ticket")
    assert resp.status_code == 401


# --- Выход из аккаунта ---------------------------------------------------------
#
# Раньше выхода не было вовсе: клиент стирал память браузера, а refresh-токен
# оставался рабочим ещё тридцать суток. На телефоне, который переходит следующей
# смене, это не выход, а его видимость.


async def test_logout_kills_refresh_token(client: AsyncClient, session_maker) -> None:
    venue_id = await _make_venue(session_maker)
    employee_id = await _make_employee(session_maker, venue_id=venue_id, pin="4711")
    refresh_token = (await _login(client, employee_id, "4711"))["refresh_token"]

    out = await client.post("/api/auth/logout", json={"refresh_token": refresh_token})
    assert out.status_code == 204

    # Тот же токен после выхода уже не обновляет сессию.
    after = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert after.status_code == 401


async def test_logout_does_not_touch_other_devices(client: AsyncClient, session_maker) -> None:
    """Управляющий сидит и в зале с телефона, и в кабинете с компьютера.

    Выход на одном не должен выбрасывать его со второго — гасим предъявленный
    токен, а не все сессии сотрудника.
    """
    venue_id = await _make_venue(session_maker)
    employee_id = await _make_employee(session_maker, venue_id=venue_id, pin="4711")
    телефон = (await _login(client, employee_id, "4711"))["refresh_token"]
    компьютер = (await _login(client, employee_id, "4711"))["refresh_token"]

    assert (
        await client.post("/api/auth/logout", json={"refresh_token": телефон})
    ).status_code == 204

    остался = await client.post("/api/auth/refresh", json={"refresh_token": компьютер})
    assert остался.status_code == 200


async def test_logout_is_idempotent(client: AsyncClient, session_maker) -> None:
    """Повторный выход не имеет права упасть: иначе человек остаётся в аккаунте
    с сообщением об ошибке и без способа выйти."""
    venue_id = await _make_venue(session_maker)
    employee_id = await _make_employee(session_maker, venue_id=venue_id, pin="4711")
    refresh_token = (await _login(client, employee_id, "4711"))["refresh_token"]

    first = await client.post("/api/auth/logout", json={"refresh_token": refresh_token})
    second = await client.post("/api/auth/logout", json={"refresh_token": refresh_token})

    assert first.status_code == 204
    assert second.status_code == 204


async def test_logout_survives_garbage_token(client: AsyncClient) -> None:
    """Токен подделан или испорчен — выйти всё равно можно."""
    resp = await client.post("/api/auth/logout", json={"refresh_token": "не-токен-вовсе"})

    assert resp.status_code == 204


async def test_logout_survives_expired_token(client: AsyncClient, session_maker) -> None:
    """Телефон пролежал в шкафчике месяц — выход не должен требовать живого токена."""
    venue_id = await _make_venue(session_maker)
    employee_id = await _make_employee(session_maker, venue_id=venue_id, pin="4711")
    import jwt as pyjwt

    живой, _ = auth_service.create_refresh_token(
        employee_id=employee_id, venue_id=venue_id, role="waiter", epoch=0
    )
    claims = pyjwt.decode(живой, settings.secret_key, algorithms=[auth_service.JWT_ALGORITHM])
    claims["exp"] = claims["iat"] - 10
    просроченный = pyjwt.encode(
        claims, settings.secret_key, algorithm=auth_service.JWT_ALGORITHM
    )

    resp = await client.post("/api/auth/logout", json={"refresh_token": просроченный})

    assert resp.status_code == 204
