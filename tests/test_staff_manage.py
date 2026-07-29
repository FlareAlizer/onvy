"""Добавление людей в смену и перевыдача доступов.

Это то, чем управляющий пользуется чаще всего после стоп-листа: пришёл новый
официант — завести и выдать PIN. Проверяем и удобные случаи, и защиту.
"""

import pytest_asyncio
from fakeredis import FakeAsyncRedis
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api import auth as auth_api
from app.api import signup as signup_api
from app.api import staff as staff_api
from app.db import Base, get_session
from app.db.models.comm_group import CommGroup, EmployeeCommGroup
from app.db.models.employee import Employee
from app.db.models.venue import Venue
from app.deps import get_redis
from app.services import auth as auth_service

УПРАВЛЯЮЩИЙ = {
    "venue_name": "Чайхана Шарк",
    "manager_name": "Гульнара Садыкова",
    "email": "rop@chayhana.ru",
    "password": "шафран-казан-пиала-97",
}


@pytest_asyncio.fixture
async def стенд():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    maker = async_sessionmaker(engine, expire_on_commit=False)
    tables = [
        Venue.__table__,
        Employee.__table__,
        CommGroup.__table__,
        EmployeeCommGroup.__table__,
    ]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)

    redis = FakeAsyncRedis(decode_responses=True)
    app = FastAPI()
    for module in (signup_api, auth_api, staff_api):
        app.include_router(module.router, prefix="/api")

    async def _session():
        async with maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def _redis():
        yield redis

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_redis] = _redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Каждый тест начинается с заведения, у которого есть управляющий.
        рег = (await client.post("/api/signup/venue", json=УПРАВЛЯЮЩИЙ)).json()
        заголовки = {"Authorization": f"Bearer {рег['access_token']}"}
        yield client, заголовки, рег["venue_id"], maker

    await redis.aclose()
    await engine.dispose()


class TestДобавление:
    async def test_официант_без_почты_получает_pin(self, стенд):
        client, заголовки, vid, _ = стенд

        resp = await client.post(
            f"/api/venues/{vid}/staff",
            json={"name": "Азизбек Рахматуллаев", "role": "waiter", "language": "uz",
                  "nickname": "Азиз"},
            headers=заголовки,
        )

        assert resp.status_code == 201
        данные = resp.json()
        assert len(данные["pin"]) == 4
        assert данные["password"] is None  # почты нет — пароль не нужен
        assert данные["nickname"] == "Азиз"

    async def test_с_почтой_выдаётся_и_пароль(self, стенд):
        client, заголовки, vid, _ = стенд

        resp = await client.post(
            f"/api/venues/{vid}/staff",
            json={"name": "Динара Абаева", "role": "host", "language": "kk",
                  "email": "hostes@chayhana.ru"},
            headers=заголовки,
        )

        данные = resp.json()
        assert данные["pin"]
        assert данные["password"] and len(данные["password"]) > 8
        assert данные["email"] == "hostes@chayhana.ru"

    async def test_выданным_pin_можно_войти(self, стенд):
        client, заголовки, vid, _ = стенд
        доступ = (
            await client.post(
                f"/api/venues/{vid}/staff",
                json={"name": "Сергей Иванов", "role": "bar"},
                headers=заголовки,
            )
        ).json()

        resp = await client.post(
            "/api/auth/login",
            json={"employee_id": доступ["employee_id"], "pin": доступ["pin"]},
        )

        assert resp.status_code == 200

    async def test_выданным_паролем_можно_войти(self, стенд):
        client, заголовки, vid, _ = стенд
        доступ = (
            await client.post(
                f"/api/venues/{vid}/staff",
                json={"name": "Динара", "role": "host", "email": "d@chayhana.ru"},
                headers=заголовки,
            )
        ).json()

        resp = await client.post(
            "/api/auth/login-email",
            json={"email": доступ["email"], "password": доступ["password"]},
        )

        assert resp.status_code == 200

    async def test_новичок_попадает_в_группы_связи(self, стенд):
        """Без групп человека не будет слышно в рации."""
        from sqlalchemy import select

        client, заголовки, vid, maker = стенд
        доступ = (
            await client.post(
                f"/api/venues/{vid}/staff",
                json={"name": "Улугбек", "role": "kitchen"},
                headers=заголовки,
            )
        ).json()

        async with maker() as session:
            связки = (
                (
                    await session.execute(
                        select(CommGroup.name)
                        .join(
                            EmployeeCommGroup,
                            EmployeeCommGroup.comm_group_id == CommGroup.id,
                        )
                        .where(EmployeeCommGroup.employee_id == доступ["employee_id"])
                    )
                )
                .scalars()
                .all()
            )

        assert set(связки) == {"кухня", "все"}

    async def test_новичок_появляется_в_ростере(self, стенд):
        client, заголовки, vid, _ = стенд
        await client.post(
            f"/api/venues/{vid}/staff",
            json={"name": "Марина Петрова", "role": "waiter"},
            headers=заголовки,
        )

        ростер = (await client.get(f"/api/venues/{vid}/staff", headers=заголовки)).json()

        assert any(e["name"] == "Марина Петрова" for e in ростер)


class TestЗащита:
    async def test_тёзка_без_уточнения_отклоняется(self, стенд):
        client, заголовки, vid, _ = стенд
        тело = {"name": "Азиз", "role": "waiter"}
        await client.post(f"/api/venues/{vid}/staff", json=тело, headers=заголовки)

        resp = await client.post(f"/api/venues/{vid}/staff", json=тело, headers=заголовки)

        assert resp.status_code == 409

    async def test_кличка_совпадающая_с_отделом_отклоняется(self, стенд):
        """С кличкой «Бар» фраза «бар, два чая» перестала бы работать."""
        client, заголовки, vid, _ = стенд

        resp = await client.post(
            f"/api/venues/{vid}/staff",
            json={"name": "Сергей", "role": "bar", "nickname": "Бар"},
            headers=заголовки,
        )

        assert resp.status_code == 422
        assert "служебн" in resp.json()["detail"]

    async def test_занятая_почта_отклоняется(self, стенд):
        client, заголовки, vid, _ = стенд

        resp = await client.post(
            f"/api/venues/{vid}/staff",
            json={"name": "Кто-то", "role": "waiter", "email": УПРАВЛЯЮЩИЙ["email"]},
            headers=заголовки,
        )

        assert resp.status_code == 409

    async def test_неизвестная_роль_отклоняется(self, стенд):
        client, заголовки, vid, _ = стенд

        resp = await client.post(
            f"/api/venues/{vid}/staff",
            json={"name": "Кто-то", "role": "директор"},
            headers=заголовки,
        )

        assert resp.status_code == 422

    async def test_официант_не_может_добавлять_людей(self, стенд):
        client, заголовки, vid, _ = стенд
        доступ = (
            await client.post(
                f"/api/venues/{vid}/staff",
                json={"name": "Азиз", "role": "waiter"},
                headers=заголовки,
            )
        ).json()
        токен = (
            await client.post(
                "/api/auth/login",
                json={"employee_id": доступ["employee_id"], "pin": доступ["pin"]},
            )
        ).json()["access_token"]

        resp = await client.post(
            f"/api/venues/{vid}/staff",
            json={"name": "Ещё кто-то", "role": "waiter"},
            headers={"Authorization": f"Bearer {токен}"},
        )

        assert resp.status_code == 403


class TestПеревыдача:
    async def test_новый_pin_работает_а_старый_нет(self, стенд):
        client, заголовки, vid, _ = стенд
        доступ = (
            await client.post(
                f"/api/venues/{vid}/staff",
                json={"name": "Азиз", "role": "waiter"},
                headers=заголовки,
            )
        ).json()
        старый_pin = доступ["pin"]

        новый = (
            await client.post(
                f"/api/venues/{vid}/staff/{доступ['employee_id']}/reset-access",
                headers=заголовки,
            )
        ).json()

        assert новый["pin"] != старый_pin
        вход_новым = await client.post(
            "/api/auth/login",
            json={"employee_id": доступ["employee_id"], "pin": новый["pin"]},
        )
        assert вход_новым.status_code == 200

        вход_старым = await client.post(
            "/api/auth/login",
            json={"employee_id": доступ["employee_id"], "pin": старый_pin},
        )
        assert вход_старым.status_code == 401

    async def test_пароль_перевыдаётся_только_при_наличии_почты(self, стенд):
        client, заголовки, vid, _ = стенд
        без_почты = (
            await client.post(
                f"/api/venues/{vid}/staff",
                json={"name": "Азиз", "role": "waiter"},
                headers=заголовки,
            )
        ).json()

        новый = (
            await client.post(
                f"/api/venues/{vid}/staff/{без_почты['employee_id']}/reset-access",
                headers=заголовки,
            )
        ).json()

        assert новый["pin"]
        assert новый["password"] is None

    async def test_чужого_сотрудника_нельзя(self, стенд):
        client, заголовки, vid, _ = стенд

        resp = await client.post(
            f"/api/venues/{vid}/staff/99999/reset-access", headers=заголовки
        )

        assert resp.status_code == 404


async def test_пароль_и_pin_не_хранятся_в_открытом_виде(стенд):
    client, заголовки, vid, maker = стенд
    доступ = (
        await client.post(
            f"/api/venues/{vid}/staff",
            json={"name": "Динара", "role": "host", "email": "d@chayhana.ru"},
            headers=заголовки,
        )
    ).json()

    async with maker() as session:
        employee = await session.get(Employee, доступ["employee_id"])

    assert доступ["pin"] not in employee.pin_hash
    assert доступ["password"] not in (employee.password_hash or "")
    assert auth_service.verify_pin(доступ["pin"], employee.pin_hash)
