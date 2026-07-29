"""REST тестов обучения: права/venue-скоуп (реально прогоняются на SQLite) +
сквозной сценарий создать/назначить/пройти/результат (нужна настоящая
Postgres-БД — test_questions.options и test_results.answers это JSONB,
SQLite её не рендерит, см. tests/test_menu_api.py для того же паттерна на
menu_items.allergens).
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
from app.api import training as training_api
from app.config import settings
from app.db import Base, get_session
from app.db.models.employee import Employee
from app.db.models.venue import Venue
from app.deps import get_redis
from app.services import auth as auth_service

_VALID_TEST_PAYLOAD = {
    "title": "Аллергены в меню",
    "description": "Проверка знания техкарты",
    "source": "knowledge",
    "source_detail": "FAQ: аллергены",
    "pass_score": 70,
    "questions": [
        {
            "question": "Что говорить, если данных об аллергенах нет?",
            "options": ["Придумать ответ", "Сказать, что данных нет, уточнить на кухне"],
            "correct_index": 1,
            "explain": "Угадывать запрещено (spec §5 S2).",
        },
        {
            "question": "Кто ведёт стоп-лист?",
            "options": ["Официант", "Управляющий"],
            "correct_index": 1,
        },
    ],
}


# --- Стенд на SQLite: только Venue+Employee (без tests/test_questions/...) ---------


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
    app.include_router(training_api.router, prefix="/api")

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


async def test_no_token_rejected_on_list_tests(client: AsyncClient) -> None:
    resp = await client.get("/api/venues/1/tests")
    assert resp.status_code == 401


async def test_waiter_cannot_create_test(client: AsyncClient, session_maker) -> None:
    venue_id = await _make_venue(session_maker)
    waiter_id = await _make_employee(session_maker, venue_id=venue_id, pin="1111", role="waiter")
    token = await _login(client, waiter_id, "1111")

    resp = await client.post(
        f"/api/venues/{venue_id}/tests", json=_VALID_TEST_PAYLOAD, headers=_auth(token)
    )
    assert resp.status_code == 403


async def test_waiter_cannot_list_all_tests(client: AsyncClient, session_maker) -> None:
    venue_id = await _make_venue(session_maker)
    waiter_id = await _make_employee(session_maker, venue_id=venue_id, pin="1111", role="waiter")
    token = await _login(client, waiter_id, "1111")

    resp = await client.get(f"/api/venues/{venue_id}/tests", headers=_auth(token))
    assert resp.status_code == 403


async def test_waiter_cannot_assign_test(client: AsyncClient, session_maker) -> None:
    venue_id = await _make_venue(session_maker)
    waiter_id = await _make_employee(session_maker, venue_id=venue_id, pin="1111", role="waiter")
    token = await _login(client, waiter_id, "1111")

    resp = await client.post(
        f"/api/venues/{venue_id}/tests/1/assign",
        json={"employee_ids": [waiter_id]},
        headers=_auth(token),
    )
    assert resp.status_code == 403


async def test_waiter_cannot_view_test_results(client: AsyncClient, session_maker) -> None:
    venue_id = await _make_venue(session_maker)
    waiter_id = await _make_employee(session_maker, venue_id=venue_id, pin="1111", role="waiter")
    token = await _login(client, waiter_id, "1111")

    resp = await client.get(f"/api/venues/{venue_id}/tests/1/results", headers=_auth(token))
    assert resp.status_code == 403


async def test_manager_of_other_venue_cannot_create_test(
    client: AsyncClient, session_maker
) -> None:
    venue_a = await _make_venue(session_maker, name="Точка А")
    venue_b = await _make_venue(session_maker, name="Точка Б")
    manager_b = await _make_manager(session_maker, venue_b, pin="9999")
    token = await _login(client, manager_b, "9999")

    resp = await client.post(
        f"/api/venues/{venue_a}/tests", json=_VALID_TEST_PAYLOAD, headers=_auth(token)
    )
    assert resp.status_code == 403


async def test_correct_index_out_of_range_is_rejected_with_422(
    client: AsyncClient, session_maker
) -> None:
    venue_id = await _make_venue(session_maker)
    manager_id = await _make_manager(session_maker, venue_id)
    token = await _login(client, manager_id, "9999")

    bad_payload = {
        **_VALID_TEST_PAYLOAD,
        "questions": [
            {"question": "Вопрос", "options": ["А", "Б"], "correct_index": 5},
        ],
    }
    resp = await client.post(
        f"/api/venues/{venue_id}/tests", json=bad_payload, headers=_auth(token)
    )
    assert resp.status_code == 422


async def test_unknown_source_is_rejected_with_422(client: AsyncClient, session_maker) -> None:
    venue_id = await _make_venue(session_maker)
    manager_id = await _make_manager(session_maker, venue_id)
    token = await _login(client, manager_id, "9999")

    resp = await client.post(
        f"/api/venues/{venue_id}/tests",
        json={**_VALID_TEST_PAYLOAD, "source": "made-up"},
        headers=_auth(token),
    )
    assert resp.status_code == 422


# =================================================================================
# Ниже — сквозной сценарий: создать/назначить/пройти/результат. Нужна настоящая
# Postgres-БД (test_questions.options, test_results.answers — JSONB, SQLite её
# не рендерит). НЕ ПРОГНАНО на этой машине — Postgres недоступен (см. отчёт лупа);
# pg_session_maker сам себя скипает.
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
    app.include_router(training_api.router, prefix="/api")

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
async def test_full_lifecycle_create_assign_submit_results(
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
        f"/api/venues/{venue_id}/tests", json=_VALID_TEST_PAYLOAD, headers=_auth(manager_token)
    )
    assert created.status_code == 201, created.text
    test_id = created.json()["id"]
    assert created.json()["assigned_employee_ids"] == []
    assert len(created.json()["questions"]) == 2

    # До назначения — submit не проходит.
    early_submit = await pg_client.post(
        f"/api/venues/{venue_id}/tests/{test_id}/submit",
        json={"answers": [1, 1]},
        headers=_auth(waiter_token),
    )
    assert early_submit.status_code == 403

    assigned = await pg_client.post(
        f"/api/venues/{venue_id}/tests/{test_id}/assign",
        json={"employee_ids": [waiter_id]},
        headers=_auth(manager_token),
    )
    assert assigned.status_code == 200
    assert assigned.json()["assigned_employee_ids"] == [waiter_id]

    # Повторное назначение — идемпотентно, не дублирует.
    reassigned = await pg_client.post(
        f"/api/venues/{venue_id}/tests/{test_id}/assign",
        json={"employee_ids": [waiter_id]},
        headers=_auth(manager_token),
    )
    assert reassigned.json()["assigned_employee_ids"] == [waiter_id]

    mine = await pg_client.get(f"/api/venues/{venue_id}/tests/mine", headers=_auth(waiter_token))
    assert mine.status_code == 200
    mine_body = mine.json()
    assert len(mine_body) == 1
    assert mine_body[0]["completed"] is False
    # Сотрудник не должен видеть правильный ответ до прохождения.
    assert "correct_index" not in mine_body[0]["questions"][0]

    submit = await pg_client.post(
        f"/api/venues/{venue_id}/tests/{test_id}/submit",
        json={"answers": [1, 0]},  # первый верный, второй неверный
        headers=_auth(waiter_token),
    )
    assert submit.status_code == 200, submit.text
    result = submit.json()
    assert result["score_percent"] == 50
    assert result["passed"] is False  # pass_score=70
    assert result["review"][0]["is_correct"] is True
    assert result["review"][1]["is_correct"] is False
    assert result["review"][1]["correct_index"] == 1

    # Повторная попытка — 409, результат не переписывается молча.
    resubmit = await pg_client.post(
        f"/api/venues/{venue_id}/tests/{test_id}/submit",
        json={"answers": [1, 1]},
        headers=_auth(waiter_token),
    )
    assert resubmit.status_code == 409

    results = await pg_client.get(
        f"/api/venues/{venue_id}/tests/{test_id}/results", headers=_auth(manager_token)
    )
    assert results.status_code == 200
    assert results.json() == [
        {
            "employee_id": waiter_id,
            "score_percent": 50,
            "passed": False,
            "completed_at": result["completed_at"],
        }
    ]


@pytest.mark.needs_db
async def test_unassigned_employee_cannot_submit(pg_client: AsyncClient, pg_session_maker) -> None:
    venue_id = await _make_venue(pg_session_maker)
    manager_id = await _make_manager(pg_session_maker, venue_id)
    waiter_id = await _make_employee(
        pg_session_maker, venue_id=venue_id, pin="1111", role="waiter"
    )
    manager_token = await _login(pg_client, manager_id, "9999")
    waiter_token = await _login(pg_client, waiter_id, "1111")

    created = await pg_client.post(
        f"/api/venues/{venue_id}/tests", json=_VALID_TEST_PAYLOAD, headers=_auth(manager_token)
    )
    test_id = created.json()["id"]

    resp = await pg_client.post(
        f"/api/venues/{venue_id}/tests/{test_id}/submit",
        json={"answers": [1, 1]},
        headers=_auth(waiter_token),
    )
    assert resp.status_code == 403
