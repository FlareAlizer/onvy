"""Сквозная доставка реплики нескольким сотрудникам одновременно.

Главный сценарий продукта и до сих пор самый непроверенный: доставка идёт только
тем, кто **сейчас** на связи, поэтому в одиночку `delivered_to` всегда пустой, и
ни один прошлый прогон не видел, чтобы реплика реально дошла до второго человека.
Проверить это можно было только двумя устройствами в руках двух людей.

Здесь смена поднимается целиком: несколько подключённых сокетов, настоящая шина
на Redis, настоящий роут `/comms/text` (тот же путь доставки, что у голосового —
`resolve_* -> deliver -> save_utterance -> bus.publish`, см. app/api/voice.py).

Что закрывается тестом, а не живым прогоном: **настоящий перевод**. На машине
разработки ключей Yandex нет, живая проверка уходит в деградацию и видит только
контракт отказа. Здесь перевод подставной (`FakeTranslation` помечает текст
префиксом языка) — значит видно, что каждому ушёл текст на ЕГО языке, а не общий.

`tests/test_dispatch_privacy.py` рядом проверяет ту же приватность на уровне
адресации. Дублирования нет: там — кого выбрали, здесь — до кого дошло.
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import adapters
from app.adapters.fakes import FakeSynthesis, FakeTranslation
from app.api import auth as auth_api
from app.api import comms as comms_api
from app.config import settings
from app.db import Base, get_session
from app.db.models.comm_group import CommGroup, EmployeeCommGroup
from app.db.models.employee import Employee
from app.db.models.venue import Venue
from app.deps import get_redis
from app.domain.intents import Group
from app.services import auth as auth_service
from app.services import runtime

# Нужна настоящая Postgres: см. фикстуру session_maker ниже.
pytestmark = pytest.mark.needs_db

# Кто в смене: id проставляется базой по порядку.
СОСТАВ = (
    # имя,      роль,      язык, PIN,    группы
    ("Азиз", "waiter", "uz", "1111", (Group.HALL,)),
    ("Марина", "waiter", "ru", "2222", (Group.HALL,)),
    ("Улугбек", "kitchen", "uz", "3333", (Group.KITCHEN,)),
    ("Бахтиёр", "kitchen", "tg", "4444", (Group.KITCHEN,)),
    ("Гуля", "manager", "ru", "5555", ()),  # ни в одной группе — слышит по роли
)


class Сокет:
    """Телефон сотрудника: помнит всё, что ему доставили."""

    def __init__(self) -> None:
        self.принято: list[dict[str, Any]] = []

    async def send_json(self, payload: dict[str, Any]) -> None:
        self.принято.append(payload)

    @property
    def тексты(self) -> list[str]:
        return [m["text"] for m in self.принято]


@pytest_asyncio.fixture
async def session_maker() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Настоящая Postgres со всей схемой.

    SQLite здесь не годится: у `utterances` проверка single_recipient_kind написана
    на постгресовом приведении `::int`, и таблица на SQLite просто не создаётся —
    та же причина, по которой сквозные тесты меню помечены needs_db.

    Пропускает себя, если базы нет, — набор остаётся зелёным на машине без неё.
    """
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect():
            pass
    except Exception as exc:  # noqa: BLE001 — любая ошибка подключения = «БД нет»
        await engine.dispose()
        pytest.skip(f"Postgres недоступен ({exc}) — needs_db тест пропущен")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator[Redis, None]:
    client = FakeAsyncRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def смена(
    session_maker: async_sessionmaker[AsyncSession],
) -> dict[str, int]:
    """Точка, четыре группы связи и пять человек. Возвращает имя -> id."""
    async with session_maker() as session:
        venue = Venue(name="Чайхана")
        session.add(venue)
        await session.flush()

        группы = {}
        for group in Group:
            cg = CommGroup(venue_id=venue.id, name=group.value)
            session.add(cg)
            группы[group] = cg
        await session.flush()

        люди: dict[str, int] = {"venue": venue.id}
        for имя, роль, язык, pin, состав in СОСТАВ:
            employee = Employee(
                venue_id=venue.id,
                name=имя,
                nickname=имя,
                role=роль,
                language=язык,
                pin_hash=auth_service.hash_pin(pin),
            )
            session.add(employee)
            await session.flush()
            for g in состав:
                session.add(
                    EmployeeCommGroup(employee_id=employee.id, comm_group_id=группы[g].id)
                )
            люди[имя] = employee.id
        await session.commit()
    return люди


@pytest_asyncio.fixture
async def стенд(
    session_maker: async_sessionmaker[AsyncSession],
    redis_client: Redis,
    смена: dict[str, int],
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[tuple[AsyncClient, dict[str, int], dict[str, Сокет]], None]:
    """Смена на связи: у каждого свой сокет, шина поднята, перевод подставной."""
    # Настоящие Yandex-адаптеры в тестах ходили бы в сеть и падали. Подставные
    # умеют то, чего живая проверка не может: реально переводить.
    monkeypatch.setattr(adapters, "translation", lambda: FakeTranslation())
    monkeypatch.setattr(
        adapters,
        "synthesis",
        lambda: FakeSynthesis(languages=frozenset({"ru", "uz", "tg", "kk", "ky", "en"})),
    )

    app = FastAPI()
    app.include_router(auth_api.router, prefix="/api")
    app.include_router(comms_api.router, prefix="/api")

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

    # Смена выходит на связь: сокет в реестре, подписка на шине, отметка присутствия.
    bus = runtime.get_bus(redis_client)
    presence = runtime.get_presence(redis_client)
    await bus.start()

    сокеты: dict[str, Сокет] = {}
    for имя, *_ in СОСТАВ:
        сокет = Сокет()
        сокеты[имя] = сокет
        runtime.registry.add(смена[имя], сокет)  # type: ignore[arg-type]
        await bus.attach(смена[имя])
        await presence.touch(смена["venue"], смена[имя])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, смена, сокеты

    for имя, *_ in СОСТАВ:
        runtime.registry.remove(смена[имя])
    await runtime.shutdown()
    app.dependency_overrides.clear()


async def _войти(client: AsyncClient, employee_id: int, pin: str) -> dict[str, str]:
    resp = await client.post(
        "/api/auth/login", json={"employee_id": employee_id, "pin": pin}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _дождаться_доставки(сокеты: dict[str, Сокет], ожидается: int) -> None:
    """Шина асинхронная: доставка приходит не в том же тике, что ответ роута."""
    for _ in range(40):
        if sum(len(с.принято) for с in сокеты.values()) >= ожидается:
            break
        await asyncio.sleep(0.05)
    # Ещё немного — чтобы поймать лишнюю доставку тому, кому не следовало.
    await asyncio.sleep(0.1)


class TestГрупповаяРеплика:
    async def test_кухня_слышит_зал_нет(self, стенд):
        """Реплика доходит до обоих поваров и не доходит до второго официанта."""
        client, люди, сокеты = стенд
        headers = await _войти(client, люди["Марина"], "2222")

        resp = await client.post(
            "/api/comms/text",
            json={"text": "два лагмана на десятый стол", "group": "кухня"},
            headers=headers,
        )

        assert resp.status_code == 200, resp.text
        доставлено = set(resp.json()["delivered_to"])
        assert {люди["Улугбек"], люди["Бахтиёр"]} <= доставлено
        assert люди["Азиз"] not in доставлено, "официант зала не должен слышать кухню"
        assert люди["Марина"] not in доставлено, "отправитель себя не слышит"

        await _дождаться_доставки(сокеты, ожидается=3)
        assert len(сокеты["Улугбек"].принято) == 1
        assert len(сокеты["Бахтиёр"].принято) == 1
        assert сокеты["Азиз"].принято == []
        assert сокеты["Марина"].принято == []

    async def test_управляющий_слышит_смену(self, стенд):
        """По спеке §4 управляющий слышит всё, даже не состоя в группе."""
        client, люди, сокеты = стенд
        headers = await _войти(client, люди["Марина"], "2222")

        resp = await client.post(
            "/api/comms/text",
            json={"text": "гости на двенадцатый стол", "group": "кухня"},
            headers=headers,
        )

        assert люди["Гуля"] in resp.json()["delivered_to"]
        await _дождаться_доставки(сокеты, ожидается=3)
        assert len(сокеты["Гуля"].принято) == 1

    async def test_каждый_слышит_на_своём_языке(self, стенд):
        """Главный дифференциатор: узбек и таджик получают разный текст.

        Живая проверка этого показать не может — без ключей Yandex перевод
        деградирует и всем уходит оригинал.
        """
        client, люди, сокеты = стенд
        headers = await _войти(client, люди["Марина"], "2222")

        await client.post(
            "/api/comms/text",
            json={"text": "стол готов", "group": "кухня"},
            headers=headers,
        )
        await _дождаться_доставки(сокеты, ожидается=3)

        узбек = сокеты["Улугбек"].принято[0]
        таджик = сокеты["Бахтиёр"].принято[0]
        assert узбек["language"] == "uz"
        assert таджик["language"] == "tg"
        assert узбек["translated"] is True
        assert узбек["text"] != таджик["text"], "текст обязан отличаться по языкам"
        assert not узбек["translation_failed"]

    async def test_управляющему_на_его_языке_без_перевода(self, стенд):
        """Языки совпали — перевод не вызывается и не помечается."""
        client, люди, сокеты = стенд
        headers = await _войти(client, люди["Марина"], "2222")

        await client.post(
            "/api/comms/text",
            json={"text": "стол готов", "group": "кухня"},
            headers=headers,
        )
        await _дождаться_доставки(сокеты, ожидается=3)

        гуля = сокеты["Гуля"].принято[0]
        assert гуля["text"] == "стол готов"
        assert гуля["translated"] is False


class TestЛичнаяРеплика:
    async def test_доходит_только_адресату(self, стенд):
        client, люди, сокеты = стенд
        headers = await _войти(client, люди["Марина"], "2222")

        resp = await client.post(
            "/api/comms/text",
            json={"text": "подойди на секунду", "recipient_id": люди["Улугбек"]},
            headers=headers,
        )

        assert resp.json()["delivered_to"] == [люди["Улугбек"]]
        await _дождаться_доставки(сокеты, ожидается=1)
        assert len(сокеты["Улугбек"].принято) == 1

    async def test_управляющий_не_получает_копию(self, стенд):
        """Личный разговор не подслушивается руководством — свойство продукта."""
        client, люди, сокеты = стенд
        headers = await _войти(client, люди["Марина"], "2222")

        await client.post(
            "/api/comms/text",
            json={"text": "подойди на секунду", "recipient_id": люди["Улугбек"]},
            headers=headers,
        )
        await _дождаться_доставки(сокеты, ожидается=1)

        assert сокеты["Гуля"].принято == [], "управляющий не слышит личную реплику"
        assert сокеты["Бахтиёр"].принято == [], "коллега по кухне тоже не слышит"
        assert сокеты["Азиз"].принято == []


class TestУшедшиеСоСвязи:
    async def test_офлайн_не_получает(self, стенд, redis_client):
        """Устный разговор не догоняет человека через час — копить нечего."""
        client, люди, сокеты = стенд
        presence = runtime.get_presence(redis_client)
        await presence.leave(люди["venue"], люди["Бахтиёр"])

        headers = await _войти(client, люди["Марина"], "2222")
        resp = await client.post(
            "/api/comms/text",
            json={"text": "закрываем смену", "group": "кухня"},
            headers=headers,
        )

        доставлено = set(resp.json()["delivered_to"])
        assert люди["Бахтиёр"] not in доставлено
        assert люди["Улугбек"] in доставлено, "оставшийся на связи получает как обычно"

        await _дождаться_доставки(сокеты, ожидается=2)
        assert сокеты["Бахтиёр"].принято == []
