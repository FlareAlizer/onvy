"""REST меню/стоп-листа: права доступа и venue-скоуп (реально прогоняются на
SQLite, без Postgres) + сквозные сценарии CRUD/импорта/стоп-листа (нужна
настоящая Postgres-БД из-за ARRAY-колонки menu_items.allergens — SQLite её не
рендерит, см. tests/conftest.py и app/db/models/menu_item.py).

Разделение неслучайно: require_manager (роль) и сверка venue_id с путём
(require_own_venue, app/api/menu.py) выполняются ДО любого обращения к
menu_items/stop_list_entries — то есть отказ по правам можно проверить, даже
не создавая эти таблицы. Это и используется ниже: первая группа тестов реальна
и прогнана; вторая (needs_db) требует Postgres, которой на этой машине нет
(Docker/initdb недоступны — см. отчёт лупа), и самоскипается через pg_session_maker.
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api import auth as auth_api
from app.api import menu as menu_api
from app.api import stop_list as stop_list_api
from app.config import settings
from app.db import Base, get_session
from app.db.models.employee import Employee
from app.db.models.venue import Venue
from app.deps import get_redis
from app.services import auth as auth_service

_VALID_CSV = "название;цена\nЛагман;450\n".encode("cp1251")


# --- Стенд на SQLite: только Venue+Employee (без menu_items/stop_list_entries) --


@pytest_asyncio.fixture
async def session_maker() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    maker = async_sessionmaker(engine, expire_on_commit=False)
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
    app.include_router(menu_api.router, prefix="/api")
    app.include_router(stop_list_api.router, prefix="/api")

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
) -> int:
    async with session_maker() as session:
        employee = Employee(
            venue_id=venue_id, name=name, role=role, pin_hash=auth_service.hash_pin(pin)
        )
        session.add(employee)
        await session.commit()
        await session.refresh(employee)
        return employee.id


async def _make_manager(
    session_maker: async_sessionmaker[AsyncSession], venue_id: int, pin: str = "9999"
) -> int:
    return await _make_employee(session_maker, venue_id=venue_id, pin=pin, role="manager")


async def _login(client: AsyncClient, employee_id: int, pin: str) -> str:
    resp = await client.post("/api/auth/login", json={"employee_id": employee_id, "pin": pin})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- Аутентификация -------------------------------------------------------------


async def test_no_token_rejected_on_menu_list(client: AsyncClient) -> None:
    resp = await client.get("/api/venues/1/menu")
    assert resp.status_code == 401


async def test_no_token_rejected_on_stop_list(client: AsyncClient) -> None:
    resp = await client.get("/api/venues/1/stop-list")
    assert resp.status_code == 401


# --- Роль: официант не может менять меню/стоп-лист ------------------------------


async def test_waiter_cannot_create_menu_item(client: AsyncClient, session_maker) -> None:
    venue_id = await _make_venue(session_maker)
    waiter_id = await _make_employee(session_maker, venue_id=venue_id, pin="1111", role="waiter")
    token = await _login(client, waiter_id, "1111")

    resp = await client.post(
        f"/api/venues/{venue_id}/menu",
        json={"name": "Лагман", "price": "450"},
        headers=_auth(token),
    )
    assert resp.status_code == 403


async def test_waiter_cannot_update_menu_item(client: AsyncClient, session_maker) -> None:
    venue_id = await _make_venue(session_maker)
    waiter_id = await _make_employee(session_maker, venue_id=venue_id, pin="1111", role="waiter")
    token = await _login(client, waiter_id, "1111")

    resp = await client.patch(
        f"/api/venues/{venue_id}/menu/1", json={"price": "500"}, headers=_auth(token)
    )
    assert resp.status_code == 403


async def test_waiter_cannot_delete_menu_item(client: AsyncClient, session_maker) -> None:
    venue_id = await _make_venue(session_maker)
    waiter_id = await _make_employee(session_maker, venue_id=venue_id, pin="1111", role="waiter")
    token = await _login(client, waiter_id, "1111")

    resp = await client.delete(f"/api/venues/{venue_id}/menu/1", headers=_auth(token))
    assert resp.status_code == 403


async def test_waiter_cannot_import_menu(client: AsyncClient, session_maker) -> None:
    venue_id = await _make_venue(session_maker)
    waiter_id = await _make_employee(session_maker, venue_id=venue_id, pin="1111", role="waiter")
    token = await _login(client, waiter_id, "1111")

    resp = await client.post(
        f"/api/venues/{venue_id}/menu/import",
        files={"file": ("menu.csv", _VALID_CSV, "text/csv")},
        headers=_auth(token),
    )
    assert resp.status_code == 403


async def test_waiter_cannot_set_stop(client: AsyncClient, session_maker) -> None:
    venue_id = await _make_venue(session_maker)
    waiter_id = await _make_employee(session_maker, venue_id=venue_id, pin="1111", role="waiter")
    token = await _login(client, waiter_id, "1111")

    resp = await client.post(
        f"/api/venues/{venue_id}/stop-list/1/set", json={}, headers=_auth(token)
    )
    assert resp.status_code == 403


async def test_waiter_cannot_unset_stop(client: AsyncClient, session_maker) -> None:
    venue_id = await _make_venue(session_maker)
    waiter_id = await _make_employee(session_maker, venue_id=venue_id, pin="1111", role="waiter")
    token = await _login(client, waiter_id, "1111")

    resp = await client.post(f"/api/venues/{venue_id}/stop-list/1/unset", headers=_auth(token))
    assert resp.status_code == 403


async def test_waiter_cannot_view_stop_list_history(client: AsyncClient, session_maker) -> None:
    venue_id = await _make_venue(session_maker)
    waiter_id = await _make_employee(session_maker, venue_id=venue_id, pin="1111", role="waiter")
    token = await _login(client, waiter_id, "1111")

    resp = await client.get(f"/api/venues/{venue_id}/stop-list/history", headers=_auth(token))
    assert resp.status_code == 403


# --- Мультиточечность: своя точка не значит доступ к чужой ----------------------


async def test_employee_of_other_venue_cannot_list_menu(client: AsyncClient, session_maker) -> None:
    venue_a = await _make_venue(session_maker, name="Точка А")
    venue_b = await _make_venue(session_maker, name="Точка Б")
    waiter_b = await _make_employee(session_maker, venue_id=venue_b, pin="2222", role="waiter")
    token = await _login(client, waiter_b, "2222")

    resp = await client.get(f"/api/venues/{venue_a}/menu", headers=_auth(token))
    assert resp.status_code == 403


async def test_employee_of_other_venue_cannot_view_stop_list(
    client: AsyncClient, session_maker
) -> None:
    venue_a = await _make_venue(session_maker, name="Точка А")
    venue_b = await _make_venue(session_maker, name="Точка Б")
    waiter_b = await _make_employee(session_maker, venue_id=venue_b, pin="2222", role="waiter")
    token = await _login(client, waiter_b, "2222")

    resp = await client.get(f"/api/venues/{venue_a}/stop-list", headers=_auth(token))
    assert resp.status_code == 403


async def test_manager_of_other_venue_cannot_create_menu_item(
    client: AsyncClient, session_maker
) -> None:
    """Роль manager сама по себе не даёт доступа к чужой точке — venue_id решает."""
    venue_a = await _make_venue(session_maker, name="Точка А")
    venue_b = await _make_venue(session_maker, name="Точка Б")
    manager_b = await _make_employee(
        session_maker, venue_id=venue_b, pin="9999", role="manager", name="Управляющий Б"
    )
    token = await _login(client, manager_b, "9999")

    resp = await client.post(
        f"/api/venues/{venue_a}/menu",
        json={"name": "Лагман", "price": "450"},
        headers=_auth(token),
    )
    assert resp.status_code == 403


async def test_manager_of_other_venue_cannot_set_stop(client: AsyncClient, session_maker) -> None:
    venue_a = await _make_venue(session_maker, name="Точка А")
    venue_b = await _make_venue(session_maker, name="Точка Б")
    manager_b = await _make_employee(
        session_maker, venue_id=venue_b, pin="9999", role="manager", name="Управляющий Б"
    )
    token = await _login(client, manager_b, "9999")

    resp = await client.post(
        f"/api/venues/{venue_a}/stop-list/1/set", json={}, headers=_auth(token)
    )
    assert resp.status_code == 403


async def test_manager_of_other_venue_cannot_import_menu(
    client: AsyncClient, session_maker
) -> None:
    venue_a = await _make_venue(session_maker, name="Точка А")
    venue_b = await _make_venue(session_maker, name="Точка Б")
    manager_b = await _make_employee(
        session_maker, venue_id=venue_b, pin="9999", role="manager", name="Управляющий Б"
    )
    token = await _login(client, manager_b, "9999")

    resp = await client.post(
        f"/api/venues/{venue_a}/menu/import",
        files={"file": ("menu.csv", _VALID_CSV, "text/csv")},
        headers=_auth(token),
    )
    assert resp.status_code == 403


# =================================================================================
# Ниже — сквозные сценарии, которым нужна настоящая Postgres-БД (ARRAY-колонка
# menu_items.allergens не рендерится на SQLite). НЕ ПРОГНАНЫ на этой машине:
# Docker и локальный Postgres недоступны (initdb падает на кириллице в имени
# аккаунта Windows — см. отчёт лупа). pg_session_maker сам себя скипает, если
# Postgres не отвечает, поэтому набор безопасен для CI без БД.
# =================================================================================


@pytest_asyncio.fixture
async def pg_session_maker() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Настоящая Postgres-сессия с полной схемой (все таблицы, включая ARRAY).
    Пропускает тест, если Postgres недоступен — не падает красным без БД."""
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect():
            pass
    except Exception as exc:  # noqa: BLE001 — любая ошибка подключения = "БД нет"
        await engine.dispose()
        pytest.skip(f"Postgres недоступен в этом окружении ({exc}) — needs_db тест пропущен")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_client(
    pg_session_maker: async_sessionmaker[AsyncSession], redis_client: Redis
) -> AsyncGenerator[AsyncClient, None]:
    app = FastAPI()
    app.include_router(auth_api.router, prefix="/api")
    app.include_router(menu_api.router, prefix="/api")
    app.include_router(stop_list_api.router, prefix="/api")

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with pg_session_maker() as session:
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


@pytest.mark.needs_db
async def test_manager_can_create_and_read_own_menu(
    pg_client: AsyncClient, pg_session_maker
) -> None:
    venue_id = await _make_venue(pg_session_maker)
    manager_id = await _make_manager(pg_session_maker, venue_id)
    token = await _login(pg_client, manager_id, "9999")

    created = await pg_client.post(
        f"/api/venues/{venue_id}/menu",
        json={
            "name": "Лагман",
            "category": "Горячее",
            "price": "450.50",
            "allergens": ["глютен"],
        },
        headers=_auth(token),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["price"] == "450.50"
    assert body["allergens"] == ["глютен"]

    listed = await pg_client.get(f"/api/venues/{venue_id}/menu", headers=_auth(token))
    assert listed.status_code == 200
    assert len(listed.json()) == 1


@pytest.mark.needs_db
async def test_duplicate_name_is_rejected_with_409(
    pg_client: AsyncClient, pg_session_maker
) -> None:
    venue_id = await _make_venue(pg_session_maker)
    manager_id = await _make_manager(pg_session_maker, venue_id)
    token = await _login(pg_client, manager_id, "9999")

    payload = {"name": "Лагман", "price": "450"}
    first = await pg_client.post(
        f"/api/venues/{venue_id}/menu", json=payload, headers=_auth(token)
    )
    assert first.status_code == 201

    second = await pg_client.post(
        f"/api/venues/{venue_id}/menu", json=payload, headers=_auth(token)
    )
    assert second.status_code == 409


@pytest.mark.needs_db
async def test_same_name_in_different_categories_are_separate_items(
    pg_client: AsyncClient, pg_session_maker
) -> None:
    """Настоящее меню: «Чай облепиховый» стоит и в чайниках, и порционно — разная
    цена, разный выход. Раньше вторая позиция получала 409 «уже есть в меню», и
    заведение молча теряло половину карты при загрузке файла."""
    venue_id = await _make_venue(pg_session_maker)
    manager_id = await _make_manager(pg_session_maker, venue_id)
    token = await _login(pg_client, manager_id, "9999")

    чайник = await pg_client.post(
        f"/api/venues/{venue_id}/menu",
        json={"name": "Чай облепиховый", "category": "Чайники", "price": "690"},
        headers=_auth(token),
    )
    assert чайник.status_code == 201

    порция = await pg_client.post(
        f"/api/venues/{venue_id}/menu",
        json={"name": "Чай облепиховый", "category": "Порционно", "price": "250"},
        headers=_auth(token),
    )
    assert порция.status_code == 201

    listed = await pg_client.get(f"/api/venues/{venue_id}/menu", headers=_auth(token))
    assert len(listed.json()) == 2

    # А вот повтор внутри одного раздела — по-прежнему конфликт.
    повтор = await pg_client.post(
        f"/api/venues/{venue_id}/menu",
        json={"name": "Чай облепиховый", "category": "Чайники", "price": "700"},
        headers=_auth(token),
    )
    assert повтор.status_code == 409

    # Перенос позиции в раздел, где тёзка уже стоит, — тот же конфликт.
    переезд = await pg_client.patch(
        f"/api/venues/{venue_id}/menu/{порция.json()['id']}",
        json={"category": "Чайники"},
        headers=_auth(token),
    )
    assert переезд.status_code == 409


@pytest.mark.needs_db
async def test_import_keeps_same_name_across_categories_and_rejects_only_true_duplicates(
    pg_client: AsyncClient, pg_session_maker
) -> None:
    venue_id = await _make_venue(pg_session_maker)
    manager_id = await _make_manager(pg_session_maker, venue_id)
    token = await _login(pg_client, manager_id, "9999")

    файл = (
        "название;раздел;цена\n"
        "Чай облепиховый;Чайники;690\n"
        "Чай облепиховый;Порционно;250\n"
        "Чай облепиховый;Чайники;700\n"  # вот это — настоящий дубликат
    ).encode()

    preview = await pg_client.post(
        f"/api/venues/{venue_id}/menu/import",
        files={"file": ("menu.csv", файл, "text/csv")},
        headers=_auth(token),
    )
    assert preview.status_code == 200
    body = preview.json()
    assert len(body["to_create"]) == 2
    assert len(body["rejected"]) == 1
    assert body["rejected"][0]["line_number"] == 4


@pytest.mark.needs_db
async def test_patch_omitted_field_unchanged_explicit_null_resets_allergens(
    pg_client: AsyncClient, pg_session_maker
) -> None:
    """Ключевая семантика PATCH: поле отсутствует — не трогаем; поле = null —
    осознанный сброс техкарты в "данных нет" (см. app/services/menu.py update_menu_item)."""
    venue_id = await _make_venue(pg_session_maker)
    manager_id = await _make_manager(pg_session_maker, venue_id)
    token = await _login(pg_client, manager_id, "9999")

    created = await pg_client.post(
        f"/api/venues/{venue_id}/menu",
        json={"name": "Лагман", "price": "450", "allergens": ["глютен"], "spiciness": 1},
        headers=_auth(token),
    )
    item_id = created.json()["id"]

    # Патчим только цену — острота и аллергены не должны тронуться.
    patched = await pg_client.patch(
        f"/api/venues/{venue_id}/menu/{item_id}", json={"price": "500"}, headers=_auth(token)
    )
    assert patched.status_code == 200
    assert patched.json()["price"] == "500.00"
    assert patched.json()["allergens"] == ["глютен"]
    assert patched.json()["spiciness"] == 1

    # Явный null для аллергенов — осознанный сброс в "не проверялось".
    reset = await pg_client.patch(
        f"/api/venues/{venue_id}/menu/{item_id}", json={"allergens": None}, headers=_auth(token)
    )
    assert reset.status_code == 200
    assert reset.json()["allergens"] is None


@pytest.mark.needs_db
async def test_soft_deleted_item_disappears_from_listing(
    pg_client: AsyncClient, pg_session_maker
) -> None:
    venue_id = await _make_venue(pg_session_maker)
    manager_id = await _make_manager(pg_session_maker, venue_id)
    token = await _login(pg_client, manager_id, "9999")

    created = await pg_client.post(
        f"/api/venues/{venue_id}/menu",
        json={"name": "Лагман", "price": "450"},
        headers=_auth(token),
    )
    item_id = created.json()["id"]

    deleted = await pg_client.delete(f"/api/venues/{venue_id}/menu/{item_id}", headers=_auth(token))
    assert deleted.status_code == 204

    listed = await pg_client.get(f"/api/venues/{venue_id}/menu", headers=_auth(token))
    assert listed.json() == []


@pytest.mark.needs_db
async def test_dry_run_import_previews_without_writing(
    pg_client: AsyncClient, pg_session_maker
) -> None:
    """Требование задания: сначала показать план, только потом применять."""
    venue_id = await _make_venue(pg_session_maker)
    manager_id = await _make_manager(pg_session_maker, venue_id)
    token = await _login(pg_client, manager_id, "9999")

    preview = await pg_client.post(
        f"/api/venues/{venue_id}/menu/import",
        files={"file": ("menu.csv", _VALID_CSV, "text/csv")},
        headers=_auth(token),
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["applied"] is False
    assert len(body["to_create"]) == 1
    assert body["to_create"][0]["name"] == "Лагман"

    listed = await pg_client.get(f"/api/venues/{venue_id}/menu", headers=_auth(token))
    assert listed.json() == []  # dry-run ничего не применил

    applied = await pg_client.post(
        f"/api/venues/{venue_id}/menu/import?dry_run=false",
        files={"file": ("menu.csv", _VALID_CSV, "text/csv")},
        headers=_auth(token),
    )
    assert applied.status_code == 200
    assert applied.json()["applied"] is True

    listed_after = await pg_client.get(f"/api/venues/{venue_id}/menu", headers=_auth(token))
    assert len(listed_after.json()) == 1


@pytest.mark.needs_db
async def test_import_matches_existing_item_by_name_as_update(
    pg_client: AsyncClient, pg_session_maker
) -> None:
    venue_id = await _make_venue(pg_session_maker)
    manager_id = await _make_manager(pg_session_maker, venue_id)
    token = await _login(pg_client, manager_id, "9999")

    await pg_client.post(
        f"/api/venues/{venue_id}/menu",
        json={"name": "Лагман", "price": "400"},
        headers=_auth(token),
    )

    preview = await pg_client.post(
        f"/api/venues/{venue_id}/menu/import",
        files={"file": ("menu.csv", _VALID_CSV, "text/csv")},  # цена 450 в файле
        headers=_auth(token),
    )
    body = preview.json()
    assert body["to_create"] == []
    assert len(body["to_update"]) == 1
    assert body["to_update"][0]["row"]["price"] == "450"


@pytest.mark.needs_db
async def test_set_stop_is_idempotent_and_unset_requires_active_entry(
    pg_client: AsyncClient, pg_session_maker
) -> None:
    venue_id = await _make_venue(pg_session_maker)
    manager_id = await _make_manager(pg_session_maker, venue_id)
    token = await _login(pg_client, manager_id, "9999")

    created = await pg_client.post(
        f"/api/venues/{venue_id}/menu",
        json={"name": "Лагман", "price": "450"},
        headers=_auth(token),
    )
    item_id = created.json()["id"]

    first = await pg_client.post(
        f"/api/venues/{venue_id}/stop-list/{item_id}/set",
        json={"reason": "закончилось мясо"},
        headers=_auth(token),
    )
    assert first.status_code == 201
    entry_id = first.json()["id"]

    # Повторное нажатие — та же запись, не вторая строка истории.
    second = await pg_client.post(
        f"/api/venues/{venue_id}/stop-list/{item_id}/set", json={}, headers=_auth(token)
    )
    assert second.status_code == 201
    assert second.json()["id"] == entry_id

    active = await pg_client.get(f"/api/venues/{venue_id}/stop-list", headers=_auth(token))
    assert len(active.json()) == 1

    unset = await pg_client.post(
        f"/api/venues/{venue_id}/stop-list/{item_id}/unset", headers=_auth(token)
    )
    assert unset.status_code == 200
    assert unset.json()["unset_at"] is not None
    assert unset.json()["unset_by_employee_id"] is not None

    # Повторное снятие — уже не в стопе, это 409, а не тихий успех.
    repeat_unset = await pg_client.post(
        f"/api/venues/{venue_id}/stop-list/{item_id}/unset", headers=_auth(token)
    )
    assert repeat_unset.status_code == 409

    history = await pg_client.get(f"/api/venues/{venue_id}/stop-list/history", headers=_auth(token))
    assert len(history.json()) == 1  # одна запись: поставили и сняли — история есть
    assert history.json()[0]["unset_at"] is not None


@pytest.mark.needs_db
async def test_waiter_can_read_menu_and_active_stop_list(
    pg_client: AsyncClient, pg_session_maker
) -> None:
    venue_id = await _make_venue(pg_session_maker)
    manager_id = await _make_manager(pg_session_maker, venue_id)
    waiter_id = await _make_employee(
        pg_session_maker, venue_id=venue_id, pin="1111", role="waiter", name="Официант"
    )
    manager_token = await _login(pg_client, manager_id, "9999")
    waiter_token = await _login(pg_client, waiter_id, "1111")

    created = await pg_client.post(
        f"/api/venues/{venue_id}/menu",
        json={"name": "Лагман", "price": "450"},
        headers=_auth(manager_token),
    )
    item_id = created.json()["id"]
    await pg_client.post(
        f"/api/venues/{venue_id}/stop-list/{item_id}/set", json={}, headers=_auth(manager_token)
    )

    menu = await pg_client.get(f"/api/venues/{venue_id}/menu", headers=_auth(waiter_token))
    assert menu.status_code == 200
    assert len(menu.json()) == 1

    stop_list = await pg_client.get(
        f"/api/venues/{venue_id}/stop-list", headers=_auth(waiter_token)
    )
    assert stop_list.status_code == 200
    assert stop_list.json()[0]["menu_item_name"] == "Лагман"
