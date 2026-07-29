"""REST целей (KPI): права/venue-скоуп (реально прогоняются на SQLite) +
сквозной сценарий постановки цели с расчётом прогресса из реальных данных
(нужна настоящая Postgres-БД).

Разделение — та же идиома, что tests/test_menu_api.py: любой успешный ответ
эндпоинта KPI считает прогресс через app/services/stats.employee_stats(),
а та безусловно читает и utterances, и assistant_queries; utterances.checks
использует Postgres-специфичный `::int`-каст (см. app/db/models/utterance.py),
поэтому даже пустая таблица utterances не создаётся на SQLite. Отказы по
роли/venue/валидации тела — успевают сработать раньше, чем KPI-эндпоинт
читает данные, поэтому прогоняются реально; сквозной сценарий помечен
needs_db и самоскипается без Postgres (её на этой машине нет — см. отчёт лупа).
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api import auth as auth_api
from app.api import kpi as kpi_api
from app.config import settings
from app.db import Base, get_session
from app.db.models.assistant_query import AssistantQuery
from app.db.models.employee import Employee
from app.db.models.venue import Venue
from app.deps import get_redis
from app.services import auth as auth_service

# --- Стенд на SQLite: только Venue+Employee (без kpis/utterances/assistant_queries) --


@pytest_asyncio.fixture
async def session_maker() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[Venue.__table__, Employee.__table__])
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
    app.include_router(kpi_api.router, prefix="/api")

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
    return await _make_employee(
        session_maker, venue_id=venue_id, pin=pin, role="manager", name="Управляющий"
    )


async def _login(client: AsyncClient, employee_id: int, pin: str) -> str:
    resp = await client.post("/api/auth/login", json={"employee_id": employee_id, "pin": pin})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- Права и venue-скоуп (реально прогнаны) -----------------------------------------


async def test_no_token_rejected_on_kpi_list(client: AsyncClient) -> None:
    resp = await client.get("/api/venues/1/kpi")
    assert resp.status_code == 401


async def test_waiter_cannot_set_kpi(client: AsyncClient, session_maker) -> None:
    venue_id = await _make_venue(session_maker)
    waiter_id = await _make_employee(session_maker, venue_id=venue_id, pin="1111", role="waiter")
    token = await _login(client, waiter_id, "1111")

    resp = await client.post(
        f"/api/venues/{venue_id}/employees/{waiter_id}/kpi",
        json={"metric": "dialogs", "target": "5", "period": "day"},
        headers=_auth(token),
    )
    assert resp.status_code == 403


async def test_waiter_cannot_bulk_set_kpi(client: AsyncClient, session_maker) -> None:
    venue_id = await _make_venue(session_maker)
    waiter_id = await _make_employee(session_maker, venue_id=venue_id, pin="1111", role="waiter")
    token = await _login(client, waiter_id, "1111")

    resp = await client.post(
        f"/api/venues/{venue_id}/kpi/bulk",
        json={"metric": "dialogs", "target": "5", "period": "day"},
        headers=_auth(token),
    )
    assert resp.status_code == 403


async def test_manager_of_other_venue_cannot_set_kpi(client: AsyncClient, session_maker) -> None:
    venue_a = await _make_venue(session_maker, name="Точка А")
    venue_b = await _make_venue(session_maker, name="Точка Б")
    waiter_a = await _make_employee(session_maker, venue_id=venue_a, pin="1111", role="waiter")
    manager_b = await _make_manager(session_maker, venue_b, pin="9999")
    token = await _login(client, manager_b, "9999")

    resp = await client.post(
        f"/api/venues/{venue_a}/employees/{waiter_a}/kpi",
        json={"metric": "dialogs", "target": "5", "period": "day"},
        headers=_auth(token),
    )
    assert resp.status_code == 403


async def test_unknown_metric_is_rejected_with_422(client: AsyncClient, session_maker) -> None:
    """revenue не в KPI_METRICS — нет источника (POS) для честного расчёта current."""
    venue_id = await _make_venue(session_maker)
    manager_id = await _make_manager(session_maker, venue_id)
    waiter_id = await _make_employee(session_maker, venue_id=venue_id, pin="1111", role="waiter")
    token = await _login(client, manager_id, "9999")

    resp = await client.post(
        f"/api/venues/{venue_id}/employees/{waiter_id}/kpi",
        json={"metric": "revenue", "target": "100000", "period": "day"},
        headers=_auth(token),
    )
    assert resp.status_code == 422


async def test_unknown_period_is_rejected_with_422(client: AsyncClient, session_maker) -> None:
    venue_id = await _make_venue(session_maker)
    manager_id = await _make_manager(session_maker, venue_id)
    waiter_id = await _make_employee(session_maker, venue_id=venue_id, pin="1111", role="waiter")
    token = await _login(client, manager_id, "9999")

    resp = await client.post(
        f"/api/venues/{venue_id}/employees/{waiter_id}/kpi",
        json={"metric": "dialogs", "target": "5", "period": "year"},
        headers=_auth(token),
    )
    assert resp.status_code == 422


# =================================================================================
# Ниже — сквозной сценарий, которому нужна настоящая Postgres-БД: любой успешный
# ответ KPI-эндпоинта считает прогресс через stats.employee_stats(), а та читает
# utterances (Postgres-специфичный ::int-каст в CHECK, см. tests/test_menu_api.py
# для того же паттерна на menu_items.allergens). НЕ ПРОГНАНО на этой машине —
# Postgres недоступен (см. отчёт лупа); pg_session_maker сам себя скипает.
# =================================================================================


@pytest_asyncio.fixture
async def pg_session_maker() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
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
    app.include_router(kpi_api.router, prefix="/api")

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


async def _make_assistant_query(
    pg_session_maker: async_sessionmaker[AsyncSession],
    *,
    venue_id: int,
    employee_id: int,
    found: bool,
    total_ms: int,
    created_at: datetime,
) -> None:
    async with pg_session_maker() as session:
        session.add(
            AssistantQuery(
                venue_id=venue_id,
                employee_id=employee_id,
                query_text="что в лагмане",
                answer_text="говядина, лапша, овощи",
                menu_item_found=found,
                total_ms=total_ms,
                created_at=created_at,
            )
        )
        await session.commit()


@pytest.mark.needs_db
async def test_manager_sets_kpi_and_progress_is_computed_from_real_data(
    pg_client: AsyncClient, pg_session_maker
) -> None:
    venue_id = await _make_venue(pg_session_maker)
    manager_id = await _make_manager(pg_session_maker, venue_id)
    waiter_id = await _make_employee(
        pg_session_maker, venue_id=venue_id, pin="1111", role="waiter", name="Официант"
    )
    manager_token = await _login(pg_client, manager_id, "9999")

    # "Сегодня" по часам сервера — set_kpi берёт period_start от datetime.now(UTC).date().
    created_at = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)
    on_date = created_at.date()
    # 3 вопроса к ассистенту за день, 2 из них закрыты им самим (autonomy = 2/3).
    await _make_assistant_query(
        pg_session_maker, venue_id=venue_id, employee_id=waiter_id, found=True,
        total_ms=1000, created_at=created_at,
    )
    await _make_assistant_query(
        pg_session_maker, venue_id=venue_id, employee_id=waiter_id, found=True,
        total_ms=2000, created_at=created_at,
    )
    await _make_assistant_query(
        pg_session_maker, venue_id=venue_id, employee_id=waiter_id, found=False,
        total_ms=3000, created_at=created_at,
    )

    set_resp = await pg_client.post(
        f"/api/venues/{venue_id}/employees/{waiter_id}/kpi",
        json={"metric": "dialogs", "target": "5", "period": "day", "note": "план на смену"},
        headers=_auth(manager_token),
    )
    assert set_resp.status_code == 201, set_resp.text
    kpi_id = set_resp.json()["id"]
    assert set_resp.json()["period_start"] == on_date.isoformat()

    listed = await pg_client.get(
        f"/api/venues/{venue_id}/employees/{waiter_id}/kpi", headers=_auth(manager_token)
    )
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 1
    assert body[0]["id"] == kpi_id
    assert body[0]["current"] == 3  # 3 вопроса к ассистенту в этот день
    assert body[0]["progress_percent"] == 60.0  # 3 из 5

    autonomy_resp = await pg_client.post(
        f"/api/venues/{venue_id}/employees/{waiter_id}/kpi",
        json={"metric": "autonomy", "target": "80", "period": "day"},
        headers=_auth(manager_token),
    )
    assert autonomy_resp.status_code == 201
    assert autonomy_resp.json()["current"] == round(2 / 3 * 100, 1)


@pytest.mark.needs_db
async def test_setting_kpi_twice_for_same_window_updates_not_duplicates(
    pg_client: AsyncClient, pg_session_maker
) -> None:
    venue_id = await _make_venue(pg_session_maker)
    manager_id = await _make_manager(pg_session_maker, venue_id)
    waiter_id = await _make_employee(pg_session_maker, venue_id=venue_id, pin="1111", role="waiter")
    token = await _login(pg_client, manager_id, "9999")

    first = await pg_client.post(
        f"/api/venues/{venue_id}/employees/{waiter_id}/kpi",
        json={"metric": "dialogs", "target": "5", "period": "week"},
        headers=_auth(token),
    )
    assert first.status_code == 201
    kpi_id = first.json()["id"]

    second = await pg_client.post(
        f"/api/venues/{venue_id}/employees/{waiter_id}/kpi",
        json={"metric": "dialogs", "target": "8", "period": "week", "note": "подняли план"},
        headers=_auth(token),
    )
    assert second.status_code == 201
    assert second.json()["id"] == kpi_id  # та же строка, не дубликат
    assert second.json()["target"] == "8.00"
    assert second.json()["note"] == "подняли план"

    listed = await pg_client.get(f"/api/venues/{venue_id}/kpi", headers=_auth(token))
    assert len(listed.json()) == 1


@pytest.mark.needs_db
async def test_bulk_kpi_sets_goal_for_every_active_employee(
    pg_client: AsyncClient, pg_session_maker
) -> None:
    venue_id = await _make_venue(pg_session_maker)
    manager_id = await _make_manager(pg_session_maker, venue_id)
    await _make_employee(
        pg_session_maker, venue_id=venue_id, pin="1111", role="waiter", name="Официант 1"
    )
    await _make_employee(
        pg_session_maker, venue_id=venue_id, pin="2222", role="waiter", name="Официант 2"
    )
    token = await _login(pg_client, manager_id, "9999")

    resp = await pg_client.post(
        f"/api/venues/{venue_id}/kpi/bulk",
        json={"metric": "help_requests", "target": "3", "period": "month"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    # Управляющий тоже активный сотрудник точки — цель ставится и ему тоже.
    assert len(body) == 3
    assert {item["metric"] for item in body} == {"help_requests"}


@pytest.mark.needs_db
async def test_employee_cannot_view_colleague_kpi(pg_client: AsyncClient, pg_session_maker) -> None:
    venue_id = await _make_venue(pg_session_maker)
    manager_id = await _make_manager(pg_session_maker, venue_id)
    waiter_a = await _make_employee(
        pg_session_maker, venue_id=venue_id, pin="1111", role="waiter", name="Официант А"
    )
    waiter_b = await _make_employee(
        pg_session_maker, venue_id=venue_id, pin="2222", role="waiter", name="Официант Б"
    )
    manager_token = await _login(pg_client, manager_id, "9999")
    await pg_client.post(
        f"/api/venues/{venue_id}/employees/{waiter_a}/kpi",
        json={"metric": "dialogs", "target": "5", "period": "day"},
        headers=_auth(manager_token),
    )

    token_b = await _login(pg_client, waiter_b, "2222")
    resp = await pg_client.get(
        f"/api/venues/{venue_id}/employees/{waiter_a}/kpi", headers=_auth(token_b)
    )
    assert resp.status_code == 403
