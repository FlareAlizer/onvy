"""Вход по почте и паролю — основной способ входа.

Отдельный файл, потому что у входа по почте своя поверхность атаки: адрес,
в отличие от employee_id, можно угадать, а форма входа не должна подсказывать,
кто у нас работает.
"""

from httpx import AsyncClient

from app.services import auth as auth_service

# Тестовый стек (SQLite in-memory + fake Redis + приложение только с роутером
# auth) уже собран в test_auth.py. Импортируем фикстуры, а не копируем их:
# две расходящиеся копии одного стенда — верный способ получить тест, который
# зелёный сам по себе и врёт про приложение.
from tests.test_auth import (  # noqa: F401 — фикстуры подхватываются pytest по имени
    _make_employee,
    _make_venue,
    client,
    redis_client,
    session_maker,
)

ПАРОЛЬ = "правильный-пароль-8+"


async def _сотрудник_с_почтой(
    session_maker, *, venue_id: int, email: str, password: str = ПАРОЛЬ, **kwargs
) -> int:
    """Завести сотрудника, у которого есть и PIN, и почта с паролем."""
    employee_id = await _make_employee(session_maker, venue_id=venue_id, pin="1111", **kwargs)
    from app.db.models.employee import Employee

    async with session_maker() as session:
        employee = await session.get(Employee, employee_id)
        employee.email = auth_service.normalize_email(email)
        employee.password_hash = auth_service.hash_password(password)
        await session.commit()
    return employee_id


class TestУспешныйВход:
    async def test_вход_по_почте_выдаёт_токены(self, client: AsyncClient, session_maker):
        venue_id = await _make_venue(session_maker)
        await _сотрудник_с_почтой(session_maker, venue_id=venue_id, email="rop@onvy.space")

        resp = await client.post(
            "/api/auth/login-email",
            json={"email": "rop@onvy.space", "password": ПАРОЛЬ},
        )

        assert resp.status_code == 200
        assert resp.json()["access_token"]
        assert resp.json()["refresh_token"]

    async def test_регистр_и_пробелы_в_почте_не_мешают(
        self, client: AsyncClient, session_maker
    ):
        """Автозаполнение и мобильные клавиатуры приносят и то, и другое."""
        venue_id = await _make_venue(session_maker)
        await _сотрудник_с_почтой(session_maker, venue_id=venue_id, email="rop@onvy.space")

        resp = await client.post(
            "/api/auth/login-email",
            json={"email": "  ROP@Onvy.Space  ", "password": ПАРОЛЬ},
        )

        assert resp.status_code == 200

    async def test_после_входа_видно_кто_вошёл(self, client: AsyncClient, session_maker):
        venue_id = await _make_venue(session_maker)
        await _сотрудник_с_почтой(
            session_maker, venue_id=venue_id, email="boss@onvy.space", role="manager"
        )
        tokens = (
            await client.post(
                "/api/auth/login-email",
                json={"email": "boss@onvy.space", "password": ПАРОЛЬ},
            )
        ).json()

        resp = await client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )

        assert resp.status_code == 200
        assert resp.json()["role"] == "manager"
        assert resp.json()["email"] == "boss@onvy.space"
        assert resp.json()["venue_id"] == venue_id


class TestОтказы:
    async def test_неверный_пароль(self, client: AsyncClient, session_maker):
        venue_id = await _make_venue(session_maker)
        await _сотрудник_с_почтой(session_maker, venue_id=venue_id, email="rop@onvy.space")

        resp = await client.post(
            "/api/auth/login-email",
            json={"email": "rop@onvy.space", "password": "не-тот-пароль"},
        )

        assert resp.status_code == 401

    async def test_несуществующая_почта_отвечает_ровно_так_же(
        self, client: AsyncClient, session_maker
    ):
        """Иначе по форме входа можно перебрать, кто у нас работает."""
        venue_id = await _make_venue(session_maker)
        await _сотрудник_с_почтой(session_maker, venue_id=venue_id, email="rop@onvy.space")

        неверный_пароль = await client.post(
            "/api/auth/login-email",
            json={"email": "rop@onvy.space", "password": "не-тот-пароль"},
        )
        нет_такой_почты = await client.post(
            "/api/auth/login-email",
            json={"email": "postoronniy@onvy.space", "password": "не-тот-пароль"},
        )

        assert неверный_пароль.status_code == нет_такой_почты.status_code == 401
        assert неверный_пароль.json() == нет_такой_почты.json()

    async def test_сотрудник_без_почты_не_войдёт_пустым_паролем(
        self, client: AsyncClient, session_maker
    ):
        """У линейного персонала почты нет — вход только по PIN, и это не дыра."""
        venue_id = await _make_venue(session_maker)
        await _make_employee(session_maker, venue_id=venue_id, pin="2222")

        resp = await client.post(
            "/api/auth/login-email",
            json={"email": "", "password": ПАРОЛЬ},
        )

        assert resp.status_code in (401, 422)

    async def test_уволенный_не_войдёт(self, client: AsyncClient, session_maker):
        from datetime import UTC, datetime

        from app.db.models.employee import Employee

        venue_id = await _make_venue(session_maker)
        employee_id = await _сотрудник_с_почтой(
            session_maker, venue_id=venue_id, email="byvshiy@onvy.space"
        )
        async with session_maker() as session:
            employee = await session.get(Employee, employee_id)
            employee.deleted_at = datetime.now(UTC)
            await session.commit()

        resp = await client.post(
            "/api/auth/login-email",
            json={"email": "byvshiy@onvy.space", "password": ПАРОЛЬ},
        )

        assert resp.status_code == 401

    async def test_короткий_пароль_не_принимается(self, client: AsyncClient):
        resp = await client.post(
            "/api/auth/login-email", json={"email": "a@onvy.space", "password": "123"}
        )

        assert resp.status_code == 422

    async def test_подбор_пароля_блокируется(self, client: AsyncClient, session_maker):
        venue_id = await _make_venue(session_maker)
        await _сотрудник_с_почтой(session_maker, venue_id=venue_id, email="rop@onvy.space")

        for _ in range(6):
            await client.post(
                "/api/auth/login-email",
                json={"email": "rop@onvy.space", "password": "перебор-перебор"},
            )

        # Даже правильный пароль теперь не пройдёт — сработала блокировка.
        resp = await client.post(
            "/api/auth/login-email",
            json={"email": "rop@onvy.space", "password": ПАРОЛЬ},
        )

        assert resp.status_code == 429


class TestОбаСпособаРаботают:
    async def test_один_и_тот_же_человек_входит_и_по_pin_и_по_почте(
        self, client: AsyncClient, session_maker
    ):
        """Смена входит по PIN, руководитель — по почте. Оба ведут в один кабинет."""
        venue_id = await _make_venue(session_maker)
        employee_id = await _сотрудник_с_почтой(
            session_maker, venue_id=venue_id, email="oba@onvy.space"
        )

        по_почте = await client.post(
            "/api/auth/login-email", json={"email": "oba@onvy.space", "password": ПАРОЛЬ}
        )
        по_pin = await client.post(
            "/api/auth/login", json={"employee_id": employee_id, "pin": "1111"}
        )

        assert по_почте.status_code == 200
        assert по_pin.status_code == 200
