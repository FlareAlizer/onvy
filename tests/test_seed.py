"""Подготовка точки к пилоту (scripts/seed_venue.py, app/db/seed.py).

Три уровня проверки, честно разделённые:

1. Чистая логика (PIN, разбор конфига, разбор аргументов CLI, форматирование
   роспечатки) — реальные тесты, без БД вообще.
2. Сидинг venue/comm_group/employee — реальные тесты на SQLite in-memory:
   ни одна из этих таблиц не использует Postgres-специфичные типы (ARRAY у
   menu_items здесь не участвует), поэтому это не имитация, а настоящий
   прогон той же ORM-логики (см. tests/test_auth.py — тот же приём).
3. Импорт CSV меню (app.services.menu.import_menu_csv трогает menu_items.
   allergens — Postgres ARRAY, SQLite её не рендерит) — помечено needs_db и
   самоскипается через pg_session_maker, если Postgres недоступен (см.
   tests/test_menu_api.py — тот же приём). На этой машине Postgres
   недоступен (Docker/initdb — см. отчёт лупа), поэтому эта группа тестов
   НЕ прогнана здесь; см. вывод pytest внизу отчёта.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import scripts.seed_venue as seed_cli
from app.config import settings
from app.db import Base
from app.db.models.comm_group import CommGroup, EmployeeCommGroup
from app.db.models.employee import Employee
from app.db.models.menu_item import MenuItem
from app.db.models.venue import Venue
from app.db.seed import (
    CreatedStaffEntry,
    PinCollisionError,
    VenueSeedConfig,
    VenueSeedResult,
    _assert_unique_pins,
    ensure_comm_groups,
    ensure_venue,
    format_pin_roster,
    generate_unique_pins,
    load_venue_seed_config,
    parse_staff_spec,
    seed_venue,
)
from app.domain.intents import Group
from app.services.auth import verify_pin
from app.services.menu import import_menu_csv

# ============================================================================
# 1. Чистая логика — без БД
# ============================================================================


class TestГенерацияPIN:
    def test_возвращает_нужное_количество_4значных_кодов(self):
        pins = generate_unique_pins(7)
        assert len(pins) == 7
        assert all(len(p) == 4 and p.isdigit() for p in pins)

    def test_коды_различны(self):
        pins = generate_unique_pins(200)  # больше, чем реально нужно на смену
        assert len(set(pins)) == len(pins)

    def test_ноль_кодов_ок(self):
        assert generate_unique_pins(0) == []

    def test_отрицательное_количество_падает(self):
        with pytest.raises(ValueError):
            generate_unique_pins(-1)

    def test_больше_чем_10000_падает(self):
        with pytest.raises(ValueError):
            generate_unique_pins(10_001)

    def test_проверка_уникальности_ловит_дубликаты(self):
        """_assert_unique_pins — защитная сетка на случай, если способ генерации
        когда-нибудь заменят на менее строгий (см. docstring PinCollisionError)."""
        with pytest.raises(PinCollisionError):
            _assert_unique_pins(["1234", "5678", "1234"])

    def test_проверка_уникальности_молчит_на_уникальных(self):
        _assert_unique_pins(["1234", "5678", "0000"])  # не должно бросить


class TestРазборСотрудника:
    def test_валидная_запись(self):
        spec = parse_staff_spec({"name": "Азиз", "role": "waiter", "language": "ru"})
        assert spec.name == "Азиз"
        assert spec.role == "waiter"
        assert spec.language == "ru"

    def test_пустое_имя_падает(self):
        with pytest.raises(ValueError, match="имя"):
            parse_staff_spec({"name": "", "role": "waiter", "language": "ru"})

    def test_неизвестная_роль_падает(self):
        with pytest.raises(ValueError, match="роль"):
            parse_staff_spec({"name": "Азиз", "role": "директор", "language": "ru"})

    def test_неизвестный_язык_падает(self):
        with pytest.raises(ValueError, match="язык"):
            parse_staff_spec({"name": "Азиз", "role": "waiter", "language": "fr"})

    def test_номер_записи_попадает_в_сообщение(self):
        with pytest.raises(ValueError, match=r"запись 3"):
            parse_staff_spec({"name": "", "role": "waiter", "language": "ru"}, line=3)

    def test_кличка_необязательна(self):
        spec = parse_staff_spec({"name": "Азиз", "role": "waiter", "language": "ru"})
        assert spec.nickname is None

    def test_кличка_подхватывается(self):
        spec = parse_staff_spec(
            {"name": "Азизбек Рахматуллаев", "role": "waiter", "language": "ru", "nickname": "Азиз"}
        )
        assert spec.nickname == "Азиз"


def _write_config(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "venue.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


_VALID_CONFIG = {
    "venue": {"name": "Чайхана Шарк", "timezone": "Asia/Yekaterinburg", "default_language": "ru"},
    "staff": [
        {"name": "Азизбек Рахматуллаев", "role": "waiter", "language": "ru", "nickname": "Азиз"},
        {"name": "Улугбек", "role": "kitchen", "language": "uz"},
        {"name": "Марина Петровна", "role": "manager", "language": "ru"},
    ],
}


class TestКонфигТочки:
    def test_валидный_конфиг_разбирается(self, tmp_path: Path):
        config = load_venue_seed_config(_write_config(tmp_path, _VALID_CONFIG))
        assert config.venue_name == "Чайхана Шарк"
        assert config.timezone == "Asia/Yekaterinburg"
        assert config.default_language == "ru"
        assert len(config.staff) == 3

    def test_дефолты_если_timezone_и_язык_не_заданы(self, tmp_path: Path):
        data = {"venue": {"name": "Точка"}, "staff": _VALID_CONFIG["staff"][:1]}
        config = load_venue_seed_config(_write_config(tmp_path, data))
        assert config.timezone == "Europe/Moscow"
        assert config.default_language == "ru"

    def test_без_имени_точки_падает(self, tmp_path: Path):
        data = {"venue": {}, "staff": _VALID_CONFIG["staff"]}
        with pytest.raises(ValueError, match="venue.name"):
            load_venue_seed_config(_write_config(tmp_path, data))

    def test_пустой_персонал_падает(self, tmp_path: Path):
        data = {"venue": _VALID_CONFIG["venue"], "staff": []}
        with pytest.raises(ValueError, match="персонала не заполнено|staff пуст|нет ни одного"):
            load_venue_seed_config(_write_config(tmp_path, data))

    def test_повторяющиеся_имена_падают(self, tmp_path: Path):
        data = {
            "venue": _VALID_CONFIG["venue"],
            "staff": [
                {"name": "Азиз", "role": "waiter", "language": "ru"},
                {"name": "азиз", "role": "bar", "language": "ru"},  # тот же человек регистром иначе
            ],
        }
        with pytest.raises(ValueError, match="повторяются"):
            load_venue_seed_config(_write_config(tmp_path, data))

    def test_невалидный_язык_точки_падает(self, tmp_path: Path):
        data = {
            "venue": {"name": "Точка", "default_language": "fr"},
            "staff": _VALID_CONFIG["staff"][:1],
        }
        with pytest.raises(ValueError, match="default_language"):
            load_venue_seed_config(_write_config(tmp_path, data))


class TestРоспечаткаPIN:
    def test_с_новыми_и_пропущенными(self):
        venue = Venue(name="Чайхана Шарк")
        result = VenueSeedResult(
            venue=venue,
            venue_created=True,
            groups={},
            created_staff=[
                CreatedStaffEntry(name="Азиз", role="waiter", language="ru", pin="4821")
            ],
            skipped_staff=["Марина Петровна"],
        )
        text = format_pin_roster(result)
        assert "Азиз" in text
        assert "4821" in text
        assert "Марина Петровна" in text
        assert "раздать лично" in text

    def test_без_новых_сотрудников(self):
        venue = Venue(name="Чайхана Шарк")
        result = VenueSeedResult(
            venue=venue, venue_created=False, groups={}, created_staff=[], skipped_staff=["Азиз"]
        )
        text = format_pin_roster(result)
        assert "Новых сотрудников не создано" in text
        assert "Азиз" in text


class TestРазборАргументовCLI:
    def test_setup(self):
        args = seed_cli.build_arg_parser().parse_args(["setup", "--config", "venue.json"])
        assert args.command == "setup"
        assert args.config == Path("venue.json")

    def test_import_menu(self):
        args = seed_cli.build_arg_parser().parse_args(
            ["import-menu", "--venue-id", "1", "--csv", "menu.csv", "--dry-run"]
        )
        assert args.command == "import-menu"
        assert args.venue_id == 1
        assert args.csv == Path("menu.csv")
        assert args.dry_run is True

    def test_import_menu_без_dry_run_по_умолчанию_false(self):
        args = seed_cli.build_arg_parser().parse_args(
            ["import-menu", "--venue-id", "1", "--csv", "menu.csv"]
        )
        assert args.dry_run is False

    def test_без_команды_падает(self):
        with pytest.raises(SystemExit):
            seed_cli.build_arg_parser().parse_args([])

    def test_setup_без_config_падает(self):
        with pytest.raises(SystemExit):
            seed_cli.build_arg_parser().parse_args(["setup"])


# ============================================================================
# 2. Сидинг в БД — реальный прогон на SQLite in-memory (см. docstring модуля)
# ============================================================================


@pytest_asyncio.fixture
async def session_maker() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
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
    yield maker
    await engine.dispose()


async def test_ensure_venue_идемпотентен_и_обновляет_конфиг(session_maker):
    async with session_maker() as session:
        venue1, created1 = await ensure_venue(
            session, name="Чайхана Шарк", timezone="Europe/Moscow", default_language="ru"
        )
        await session.commit()
        assert created1 is True

        # Другой регистр в имени — та же точка, не дубль.
        venue2, created2 = await ensure_venue(
            session, name="чайхана шарк", timezone="Asia/Yekaterinburg", default_language="uz"
        )
        await session.commit()
        assert created2 is False
        assert venue2.id == venue1.id
        assert venue2.timezone == "Asia/Yekaterinburg"  # обновилось
        assert venue2.default_language == "uz"

        count = (await session.execute(select(Venue))).scalars().all()
        assert len(count) == 1


async def test_ensure_comm_groups_создаёт_четыре_и_идемпотентен(session_maker):
    async with session_maker() as session:
        venue, _ = await ensure_venue(
            session, name="Точка", timezone="Europe/Moscow", default_language="ru"
        )
        await session.flush()

        groups1 = await ensure_comm_groups(session, venue)
        await session.commit()
        assert set(groups1) == set(Group)
        assert {g.name for g in groups1.values()} == {"зал", "кухня", "бар", "все"}

        groups2 = await ensure_comm_groups(session, venue)
        await session.commit()
        assert {g.id for g in groups1.values()} == {g.id for g in groups2.values()}

        all_groups = (await session.execute(select(CommGroup))).scalars().all()
        assert len(all_groups) == 4  # не восемь


def _config(staff: list[dict], venue_name: str = "Чайхана Шарк") -> VenueSeedConfig:
    return VenueSeedConfig(
        venue_name=venue_name,
        timezone="Europe/Moscow",
        default_language="ru",
        staff=tuple(parse_staff_spec(row) for row in staff),
    )


async def test_seed_venue_создаёт_персонал_с_нужными_группами(session_maker):
    config = _config(
        [
            {
                "name": "Азизбек Рахматуллаев",
                "role": "waiter",
                "language": "ru",
                "nickname": "Азиз",
            },
            {"name": "Улугбек", "role": "kitchen", "language": "uz"},
            {"name": "Марина Петровна", "role": "manager", "language": "ru"},
        ]
    )
    async with session_maker() as session:
        result = await seed_venue(session, config)
        await session.commit()

        assert result.venue_created is True
        assert {e.name for e in result.created_staff} == {
            "Азизбек Рахматуллаев",
            "Улугбек",
            "Марина Петровна",
        }
        assert len({e.pin for e in result.created_staff}) == 3  # PIN разные

        employees = (await session.execute(select(Employee))).scalars().all()
        by_name = {e.name: e for e in employees}
        assert by_name["Азизбек Рахматуллаев"].nickname == "Азиз"
        assert by_name["Улугбек"].nickname is None  # кличку не указали — и это ок

        # PIN реально захеширован (не хранится как есть) и проверяется через verify_pin.
        pin_by_name = {e.name: e.pin for e in result.created_staff}
        for name, employee in by_name.items():
            assert employee.pin_hash != pin_by_name[name]
            assert verify_pin(pin_by_name[name], employee.pin_hash) is True

        memberships = (await session.execute(select(EmployeeCommGroup))).scalars().all()
        groups_by_employee: dict[int, set[int]] = {}
        for m in memberships:
            groups_by_employee.setdefault(m.employee_id, set()).add(m.comm_group_id)

        group_id_to_name = {g.id: g.name for g in result.groups.values()}
        waiter_groups = {
            group_id_to_name[gid]
            for gid in groups_by_employee[by_name["Азизбек Рахматуллаев"].id]
        }
        kitchen_groups = {
            group_id_to_name[gid] for gid in groups_by_employee[by_name["Улугбек"].id]
        }
        manager_groups = {
            group_id_to_name[gid] for gid in groups_by_employee[by_name["Марина Петровна"].id]
        }
        assert waiter_groups == {"зал", "все"}
        assert kitchen_groups == {"кухня", "все"}
        assert manager_groups == {"зал", "кухня", "бар", "все"}


async def test_seed_venue_повторный_запуск_не_плодит_дубли(session_maker):
    config = _config([{"name": "Азиз", "role": "waiter", "language": "ru"}])
    async with session_maker() as session:
        first = await seed_venue(session, config)
        await session.commit()
        assert len(first.created_staff) == 1
        first_pin = first.created_staff[0].pin

        second = await seed_venue(session, config)
        await session.commit()
        assert second.venue_created is False
        assert second.created_staff == []  # новый PIN не выдаётся повторно
        assert second.skipped_staff == ["Азиз"]

        employees = (await session.execute(select(Employee))).scalars().all()
        assert len(employees) == 1  # не два Азиза
        # PIN исходного сотрудника не изменился — сверяем той же plaintext-строкой.
        assert verify_pin(first_pin, employees[0].pin_hash) is True

        groups = (await session.execute(select(CommGroup))).scalars().all()
        assert len(groups) == 4  # не восемь


async def test_seed_venue_доливка_нового_сотрудника_не_трогает_старых(session_maker):
    async with session_maker() as session:
        first = await seed_venue(
            session, _config([{"name": "Азиз", "role": "waiter", "language": "ru"}])
        )
        await session.commit()

        second = await seed_venue(
            session,
            _config(
                [
                    {"name": "Азиз", "role": "waiter", "language": "ru"},
                    {"name": "Улугбек", "role": "kitchen", "language": "uz"},
                ]
            ),
        )
        await session.commit()

        assert second.skipped_staff == ["Азиз"]
        assert [e.name for e in second.created_staff] == ["Улугбек"]

        employees = (await session.execute(select(Employee))).scalars().all()
        assert {e.name for e in employees} == {"Азиз", "Улугбек"}
        assert first.venue.id == second.venue.id


async def test_run_setup_cli_печатает_pin_и_коммитит(session_maker, tmp_path, monkeypatch, capsys):
    """Проверяет реальную обвязку CLI (scripts/seed_venue.py:_run_setup), а не
    только парсинг аргументов: подменяем SessionLocal на SQLite-сессию теста."""
    monkeypatch.setattr(seed_cli, "SessionLocal", session_maker)
    config_path = _write_config(tmp_path, _VALID_CONFIG)
    args = seed_cli.build_arg_parser().parse_args(["setup", "--config", str(config_path)])

    await seed_cli._run_setup(args)

    out = capsys.readouterr().out
    assert "Чайхана Шарк" in out
    assert "создана" in out
    assert "Азиз" in out
    assert "venue_id" in out

    async with session_maker() as session:
        employees = (await session.execute(select(Employee))).scalars().all()
        assert len(employees) == 3


# ============================================================================
# 3. Импорт CSV меню — нужна настоящая Postgres (ARRAY-колонка), needs_db
# ============================================================================


@pytest_asyncio.fixture
async def pg_session_maker() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Настоящая Postgres-сессия с полной схемой. Самоскипается, если Postgres
    недоступен — тот же приём, что в tests/test_menu_api.py."""
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


_MENU_CSV = (
    "название;категория;цена;состав;аллергены;вес;время отдачи;острота\n"
    "Лагман;Горячее;450;лапша, говядина, перец;перец, глютен;350;20;2\n"
    "Чай зелёный;Напитки;120;;нет;300;3;0\n"
).encode("cp1251")


@pytest.mark.needs_db
async def test_import_menu_csv_на_реальной_схеме(pg_session_maker):
    """CSV -> план -> применение на настоящей Postgres-схеме (menu_items.allergens
    — ARRAY). Проверяет ровно то, что 30 июля должно заехать одной командой
    `seed_venue.py import-menu`."""
    async with pg_session_maker() as session:
        venue = Venue(name="Чайхана Шарк")
        session.add(venue)
        await session.commit()
        await session.refresh(venue)

        plan = await import_menu_csv(session, venue.id, _MENU_CSV, dry_run=False)
        await session.commit()

        assert len(plan.to_create) == 2
        assert plan.rejected == []

        items = (
            (await session.execute(select(MenuItem).where(MenuItem.venue_id == venue.id)))
            .scalars()
            .all()
        )
        by_name = {i.name: i for i in items}
        assert by_name["Лагман"].allergens == ["перец", "глютен"]
        assert by_name["Чай зелёный"].allergens == []  # "нет" -> подтверждено, не NULL
        assert by_name["Лагман"].composition is not None


@pytest.mark.needs_db
async def test_import_menu_csv_dry_run_не_пишет_в_бд(pg_session_maker):
    async with pg_session_maker() as session:
        venue = Venue(name="Точка")
        session.add(venue)
        await session.commit()
        await session.refresh(venue)

        plan = await import_menu_csv(session, venue.id, _MENU_CSV, dry_run=True)
        assert plan.applied is False
        assert len(plan.to_create) == 2

        items = (
            (await session.execute(select(MenuItem).where(MenuItem.venue_id == venue.id)))
            .scalars()
            .all()
        )
        assert items == []  # dry-run ничего не записал
