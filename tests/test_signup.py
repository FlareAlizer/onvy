"""Регистрация заведения — единственная форма, открытая без авторизации.

Поэтому проверяем не только «работает», но и что через неё нельзя попасть
в чужое заведение и занять чужую почту.
"""

import pytest_asyncio
from fakeredis import FakeAsyncRedis
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api import auth as auth_api
from app.api import signup as signup_api
from app.db import Base, get_session
from app.db.models.comm_group import CommGroup, EmployeeCommGroup
from app.db.models.employee import Employee
from app.db.models.venue import Venue
from app.deps import get_redis
from app.services import auth as auth_service

ЗАЯВКА = {
    "venue_name": "Чайхана Шарк",
    "manager_name": "Гульнара Садыкова",
    "email": "rop@chayhana.ru",
    "password": "шафран-казан-пиала-97",
}


@pytest_asyncio.fixture
async def стенд():
    """Приложение с регистрацией и входом на своей БД."""
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
    app.include_router(signup_api.router, prefix="/api")
    app.include_router(auth_api.router, prefix="/api")

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
        yield client, maker

    await redis.aclose()
    await engine.dispose()


class TestРегистрация:
    async def test_заведение_и_управляющий_создаются(self, стенд):
        client, _ = стенд

        resp = await client.post("/api/signup/venue", json=ЗАЯВКА)

        assert resp.status_code == 201
        данные = resp.json()
        assert данные["venue_name"] == "Чайхана Шарк"
        assert данные["access_token"] and данные["refresh_token"]

    async def test_сразу_можно_работать_без_повторного_входа(self, стенд):
        """Токены отдаются при регистрации — пароль второй раз не спрашиваем."""
        client, _ = стенд
        данные = (await client.post("/api/signup/venue", json=ЗАЯВКА)).json()

        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {данные['access_token']}"},
        )

        assert resp.status_code == 200
        assert resp.json()["role"] == "manager"
        assert resp.json()["venue_name"] == "Чайхана Шарк"

    async def test_группы_связи_создаются_сразу(self, стенд):
        """Без них рация не работает, а «настройте группы» человек не поймёт."""
        client, maker = стенд
        данные = (await client.post("/api/signup/venue", json=ЗАЯВКА)).json()

        from sqlalchemy import select

        async with maker() as session:
            названия = (
                (
                    await session.execute(
                        select(CommGroup.name).where(
                            CommGroup.venue_id == данные["venue_id"]
                        )
                    )
                )
                .scalars()
                .all()
            )
            связки = (
                (
                    await session.execute(
                        select(EmployeeCommGroup.comm_group_id).where(
                            EmployeeCommGroup.employee_id == данные["employee_id"]
                        )
                    )
                )
                .scalars()
                .all()
            )

        assert set(названия) == {"зал", "кухня", "бар", "все"}
        # Управляющий слышит всё — он во всех четырёх группах.
        assert len(связки) == 4

    async def test_после_регистрации_работает_вход_по_почте(self, стенд):
        client, _ = стенд
        await client.post("/api/signup/venue", json=ЗАЯВКА)

        resp = await client.post(
            "/api/auth/login-email",
            json={"email": ЗАЯВКА["email"], "password": ЗАЯВКА["password"]},
        )

        assert resp.status_code == 200

    async def test_у_управляющего_есть_и_pin(self, стенд):
        """Он тоже выходит в зал, а там почту вводить неудобно."""
        client, maker = стенд
        данные = (await client.post("/api/signup/venue", json=ЗАЯВКА)).json()

        async with maker() as session:
            employee = await session.get(Employee, данные["employee_id"])

        assert employee.pin_hash


class TestЗащита:
    async def test_занятая_почта_отклоняется(self, стенд):
        client, _ = стенд
        await client.post("/api/signup/venue", json=ЗАЯВКА)

        resp = await client.post(
            "/api/signup/venue", json={**ЗАЯВКА, "venue_name": "Другая чайхана"}
        )

        assert resp.status_code == 409
        assert "войти" in resp.json()["detail"]

    async def test_нельзя_зарегистрироваться_в_существующее_заведение(self, стенд):
        """Иначе любой, кто знает название чайханы, завёл бы себе там доступ."""
        client, _ = стенд
        await client.post("/api/signup/venue", json=ЗАЯВКА)

        resp = await client.post(
            "/api/signup/venue",
            json={**ЗАЯВКА, "email": "postoronniy@chayhana.ru"},
        )

        assert resp.status_code == 409
        assert "уже зарегистрировано" in resp.json()["detail"]

    async def test_название_сверяется_без_учёта_регистра(self, стенд):
        client, _ = стенд
        await client.post("/api/signup/venue", json=ЗАЯВКА)

        resp = await client.post(
            "/api/signup/venue",
            json={
                **ЗАЯВКА,
                "email": "another@chayhana.ru",
                "venue_name": "чайхана шарк",
            },
        )

        assert resp.status_code == 409

    async def test_короткий_пароль_не_принимается(self, стенд):
        client, _ = стенд

        resp = await client.post("/api/signup/venue", json={**ЗАЯВКА, "password": "123"})

        assert resp.status_code == 422

    async def test_пароль_не_хранится_в_открытом_виде(self, стенд):
        client, maker = стенд
        данные = (await client.post("/api/signup/venue", json=ЗАЯВКА)).json()

        async with maker() as session:
            employee = await session.get(Employee, данные["employee_id"])

        assert ЗАЯВКА["password"] not in (employee.password_hash or "")
        assert auth_service.verify_password(ЗАЯВКА["password"], employee.password_hash)
