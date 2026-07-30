"""Кому уходит реплика: группе или лично.

Тесты появились после прямого вопроса владельца — «как поговорить с отдельным
сотрудником, чтобы никто не слышал». Ответ по коду был «уже приватно», но
свойство ничем не защищено: одна строка в resolve_person, добавляющая
управляющего «чтобы он слышал всё», молча превратила бы личный разговор в
общий. Здесь это зафиксировано.
"""

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.db.models.comm_group import CommGroup, EmployeeCommGroup
from app.db.models.employee import Employee
from app.db.models.venue import Venue
from app.domain.intents import Group
from app.services import dispatch


class FakePresence:
    """Присутствие без Redis: кто в списке — тот на связи."""

    def __init__(self, *ids: int) -> None:
        self._ids = set(ids)

    async def online(self, venue_id: int) -> set[int]:
        return set(self._ids)


@pytest_asyncio.fixture
async def стенд():
    """Точка с четырьмя группами и сменой: официант, повар, управляющий."""
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

    async with maker() as session:
        venue = Venue(name="Чайхана")
        session.add(venue)
        await session.flush()

        группы = {}
        for group in Group:
            cg = CommGroup(venue_id=venue.id, name=group.value)
            session.add(cg)
            группы[group] = cg
        await session.flush()

        люди = {}
        for имя, роль, язык, состав in (
            ("Азиз", "waiter", "uz", (Group.HALL, Group.EVERYONE)),
            ("Шеф", "kitchen", "uz", (Group.KITCHEN, Group.EVERYONE)),
            ("Бахти", "kitchen", "tg", (Group.KITCHEN, Group.EVERYONE)),
            ("Гуля", "manager", "ru", (Group.EVERYONE,)),
        ):
            employee = Employee(
                venue_id=venue.id,
                name=имя,
                nickname=имя,
                role=роль,
                language=язык,
                pin_hash="x",
            )
            session.add(employee)
            await session.flush()
            for g in состав:
                session.add(
                    EmployeeCommGroup(
                        employee_id=employee.id, comm_group_id=группы[g].id
                    )
                )
            люди[имя] = employee.id
        await session.commit()

    async with maker() as session:
        yield session, venue.id, люди
    await engine.dispose()


class TestЛичнаяРеплика:
    async def test_уходит_ровно_одному(self, стенд):
        session, venue_id, люди = стенд
        # На связи вся смена, включая управляющего.
        presence = FakePresence(*люди.values())

        получатели = await dispatch.resolve_person(
            session, presence, venue_id=venue_id, employee_id=люди["Шеф"]
        )

        assert [r.employee_id for r in получатели] == [люди["Шеф"]]

    async def test_управляющий_не_получает_копию(self, стенд):
        """Главное свойство: личный разговор не подслушивается руководством."""
        session, venue_id, люди = стенд
        presence = FakePresence(*люди.values())

        получатели = await dispatch.resolve_person(
            session, presence, venue_id=venue_id, employee_id=люди["Азиз"]
        )

        assert люди["Гуля"] not in [r.employee_id for r in получатели]

    async def test_язык_получателя_подставляется(self, стенд):
        """Перевод идёт на язык того, кому говорят, а не отправителя."""
        session, venue_id, люди = стенд
        presence = FakePresence(*люди.values())

        получатели = await dispatch.resolve_person(
            session, presence, venue_id=venue_id, employee_id=люди["Бахти"]
        )

        assert получатели[0].language == "tg"

    async def test_офлайн_коллеге_не_доставляется(self, стенд):
        """Устный разговор не догоняет человека через час — копить нечего."""
        session, venue_id, люди = стенд
        presence = FakePresence(люди["Азиз"])  # Шеф не на связи

        получатели = await dispatch.resolve_person(
            session, presence, venue_id=venue_id, employee_id=люди["Шеф"]
        )

        assert получатели == []

    async def test_сотрудник_чужой_точки_недоступен(self, стенд):
        session, venue_id, люди = стенд
        presence = FakePresence(*люди.values())

        получатели = await dispatch.resolve_person(
            session, presence, venue_id=venue_id + 999, employee_id=люди["Шеф"]
        )

        assert получатели == []


class TestГрупповаяРеплика:
    async def test_кухня_слышит_только_кухню_и_управляющего(self, стенд):
        """Управляющий добавляется намеренно — по спеке он слышит смену."""
        session, venue_id, люди = стенд
        presence = FakePresence(*люди.values())

        получатели, _ = await dispatch.resolve_group(
            session,
            presence,
            venue_id=venue_id,
            group=Group.KITCHEN,
            exclude_id=люди["Азиз"],
        )

        ids = {r.employee_id for r in получатели}
        assert люди["Шеф"] in ids
        assert люди["Бахти"] in ids
        assert люди["Гуля"] in ids  # управляющий слышит всё
        assert люди["Азиз"] not in ids  # отправитель себя не слышит

    async def test_отправитель_исключается(self, стенд):
        session, venue_id, люди = стенд
        presence = FakePresence(*люди.values())

        получатели, _ = await dispatch.resolve_group(
            session,
            presence,
            venue_id=venue_id,
            group=Group.KITCHEN,
            exclude_id=люди["Шеф"],
        )

        assert люди["Шеф"] not in {r.employee_id for r in получатели}

    async def test_пустая_смена_не_ошибка(self, стенд):
        session, venue_id, люди = стенд
        presence = FakePresence()  # никого нет

        получатели, _ = await dispatch.resolve_group(
            session,
            presence,
            venue_id=venue_id,
            group=Group.EVERYONE,
            exclude_id=люди["Азиз"],
        )

        assert получатели == []
