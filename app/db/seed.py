"""Подготовка точки к первой смене: venue + группы связи + персонал с PIN.

Логика разбита на чистые функции (генерация PIN, разбор конфига — без базы,
проверяются юнит-тестами) и async-функции, работающие поверх уже открытой
AsyncSession (без FastAPI и без CLI — это забота scripts/seed_venue.py).

Идемпотентность продумана так, чтобы скрипт можно было безопасно запускать
повторно (например, "добавить ещё двух официантов 30 июля"):
  - venue ищется по имени (без учёта регистра) среди неудалённых; если нашли —
    переиспользуем и обновляем timezone/default_language на переданные (это
    просто конфигурация точки, не история, обновлять безопасно);
  - группы связи (Group.HALL/KITCHEN/BAR/EVERYONE) заводятся по имени в рамках
    точки, повторный запуск не создаёт вторую "кухню";
  - сотрудники сопоставляются по имени в рамках точки. Уже существующие —
    ПРОПУСКАЮТСЯ, а не обновляются: PIN уже физически роздан на смене, тихая
    перегенерация PIN при повторном запуске сделала бы вчерашний PIN нерабочим
    без предупреждения — это хуже, чем неудобство "заводить смену сотрудников
    руками, если реально сменилась роль". Смена роли/языка существующего
    сотрудника — сознательное отдельное действие (админ-API), не побочный
    эффект повторного сидинга.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.comm_group import CommGroup, EmployeeCommGroup
from app.db.models.employee import Employee
from app.db.models.enums import EMPLOYEE_ROLES, LANGUAGES
from app.db.models.venue import Venue
from app.domain.intents import Group
from app.domain.nicknames import check_nicknames
from app.services.auth import hash_password, hash_pin

# --- PIN ------------------------------------------------------------------

# 4-значный PIN: короткий и быстрый для ввода одной рукой в зале (spec §6,
# эргономика), пространство значений 0000..9999.
_PIN_SPACE = 10_000


class PinCollisionError(Exception):
    """Сгенерированные PIN пересеклись.

    Не должно происходить: generate_unique_pins берёт числа БЕЗ возврата
    (secrets.SystemRandom().sample), совпадение структурно невозможно. Проверка
    оставлена как защита на случай, если способ генерации в будущем заменят на
    менее строгий (например, generate-and-retry) — тогда именно эта проверка
    поймает баг до того, как двум сотрудникам выдадут одинаковый PIN.
    """


def generate_unique_pins(count: int) -> list[str]:
    """Сгенерировать `count` различных 4-значных PIN-кодов.

    secrets.SystemRandom().sample() — криптографически случайная выборка без
    возврата (наощь os.urandom, не random.randint()/random.sample()), поэтому
    дубликат в результате структурно невозможен — в отличие от подхода
    "сгенерировать N раз и понадеяться", здесь его негде взяться.
    """
    if count < 0:
        raise ValueError("count не может быть отрицательным")
    if count > _PIN_SPACE:
        raise ValueError(
            f"Нельзя выдать {count} различных 4-значных PIN — их всего {_PIN_SPACE}"
        )
    numbers = secrets.SystemRandom().sample(range(_PIN_SPACE), count)
    pins = [f"{n:04d}" for n in numbers]
    _assert_unique_pins(pins)
    return pins


# Пароль для входа по почте. Слова из простого словаря вместо случайных
# символов: пароль диктуют голосом и переписывают с листа, а «bK7#qZ» в этих
# условиях превращается в звонок «у меня не работает вход».
# Три слова из этого набора плюс двузначное число — свыше 10^9 вариантов,
# для входа с блокировкой после пяти попыток этого достаточно с запасом.
_PASSWORD_WORDS = (
    "чайник", "лепёшка", "тандыр", "шафран", "гранат", "казан", "изюм",
    "курага", "миндаль", "базилик", "кинза", "зира", "барбарис", "халва",
    "пиала", "дастархан", "самовар", "урюк", "кунжут", "корица",
)


def generate_password() -> str:
    """Сгенерировать пароль, который не стыдно продиктовать вслух."""
    rng = secrets.SystemRandom()
    words = rng.sample(_PASSWORD_WORDS, 3)
    return "-".join(words) + f"-{rng.randrange(10, 100)}"


def _assert_unique_pins(pins: list[str]) -> None:
    if len(set(pins)) != len(pins):
        duplicates = sorted({p for p in pins if pins.count(p) > 1})
        raise PinCollisionError(f"Сгенерированы повторяющиеся PIN: {duplicates}")


# --- Роль -> группы связи ---------------------------------------------------

# specs/pilot-chaihana.md §4: официант говорит в зал и слышит "всех"; кухня/бар —
# внутри своего цеха и "всех"; хостес — broadcast по залу; управляющий слышит всё.
ROLE_GROUPS: dict[str, tuple[Group, ...]] = {
    "waiter": (Group.HALL, Group.EVERYONE),
    "kitchen": (Group.KITCHEN, Group.EVERYONE),
    "bar": (Group.BAR, Group.EVERYONE),
    "host": (Group.HALL, Group.EVERYONE),
    "manager": (Group.HALL, Group.KITCHEN, Group.BAR, Group.EVERYONE),
}
assert set(ROLE_GROUPS) == set(EMPLOYEE_ROLES), "ROLE_GROUPS должен покрывать все роли из enums.py"


# --- Разбор конфига точки (чистая логика, без БД) ---------------------------


@dataclass(frozen=True)
class StaffSpec:
    """Одна строка списка персонала из конфига — ещё не сотрудник в БД."""

    name: str
    role: str
    language: str
    # Короткая кличка на смене ("Азиз" при полном "Азизбек Рахматуллаев") —
    # по ней голосовая маршрутизация ищет обращение в первую очередь
    # (app/domain/intents.py, Colleague). Необязательна: без неё обращение
    # ищут по первому слову полного имени.
    nickname: str | None = None
    # Почта для входа. Необязательна: у линейного персонала её может не быть,
    # им хватает быстрого входа по PIN.
    email: str | None = None


def parse_staff_spec(raw: dict, *, line: int | None = None) -> StaffSpec:
    """Разобрать и провалидировать одну запись персонала. Бросает ValueError
    с понятным сообщением — конфиг для пилота заполняет человек, не API-клиент."""
    where = f" (запись {line})" if line is not None else ""

    name = str(raw.get("name", "")).strip()
    if not name:
        raise ValueError(f"Не заполнено имя сотрудника{where}")

    role = str(raw.get("role", "")).strip()
    if role not in EMPLOYEE_ROLES:
        raise ValueError(
            f"Неизвестная роль {role!r}{where} — допустимо: {', '.join(EMPLOYEE_ROLES)}"
        )

    language = str(raw.get("language", "")).strip()
    if language not in LANGUAGES:
        raise ValueError(
            f"Неизвестный язык {language!r}{where} — допустимо: {', '.join(LANGUAGES)}"
        )

    nickname = str(raw.get("nickname") or "").strip() or None

    email = str(raw.get("email") or "").strip().lower() or None
    if email is not None and ("@" not in email or "." not in email.split("@")[-1]):
        raise ValueError(f"Почта {email!r}{where} не похожа на адрес")

    return StaffSpec(
        name=name, role=role, language=language, nickname=nickname, email=email
    )


@dataclass(frozen=True)
class VenueSeedConfig:
    """Точка + персонал для одного запуска scripts/seed_venue.py setup."""

    venue_name: str
    timezone: str
    default_language: str
    staff: tuple[StaffSpec, ...]


def load_venue_seed_config(path: Path) -> VenueSeedConfig:
    """Прочитать и провалидировать JSON-конфиг точки.

    Формат (см. docs/runbook-pilot-setup.md для полного примера):
        {
          "venue": {"name": "...", "timezone": "...", "default_language": "ru"},
          "staff": [{"name": "...", "role": "waiter", "language": "ru"}, ...]
        }
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    venue = data.get("venue") or {}
    venue_name = str(venue.get("name", "")).strip()
    if not venue_name:
        raise ValueError("В конфиге не заполнено venue.name")

    timezone = str(venue.get("timezone") or "Europe/Moscow").strip()

    default_language = str(venue.get("default_language") or "ru").strip()
    if default_language not in LANGUAGES:
        raise ValueError(
            f"Неизвестный venue.default_language: {default_language!r} — "
            f"допустимо: {', '.join(LANGUAGES)}"
        )

    raw_staff = data.get("staff") or []
    if not raw_staff:
        raise ValueError("В конфиге нет ни одного сотрудника (staff пуст)")

    staff = tuple(parse_staff_spec(row, line=i) for i, row in enumerate(raw_staff, start=1))

    # Сотрудники сопоставляются по имени (см. docstring модуля) — совпадающие
    # имена в одном конфиге сломают это сопоставление молча, лучше упасть сразу.
    names = [s.name.casefold() for s in staff]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise ValueError(
            f"В конфиге повторяются имена сотрудников: {duplicates} — "
            "добавьте фамилию или уточнение, seed различает сотрудников по имени"
        )

    emails = [s.email for s in staff if s.email]
    повторы = sorted({e for e in emails if emails.count(e) > 1})
    if повторы:
        raise ValueError(
            f"В конфиге повторяются почты: {повторы} — по почте входят, "
            "один адрес не может принадлежать двоим"
        )

    # Клички проверяем здесь же, до записи в БД: плохая кличка ломает голосовую
    # адресацию тихо — пилот запустится, а обращения начнут уезжать не туда.
    problems = check_nicknames([s.nickname for s in staff])
    if problems:
        raise ValueError(
            "Клички не годятся для голосового обращения:\n  "
            + "\n  ".join(str(problem) for problem in problems)
        )

    return VenueSeedConfig(
        venue_name=venue_name,
        timezone=timezone,
        default_language=default_language,
        staff=staff,
    )


# --- Сидинг в БД -------------------------------------------------------------


async def ensure_venue(
    session: AsyncSession, *, name: str, timezone: str, default_language: str
) -> tuple[Venue, bool]:
    """Найти точку по имени (без учёта регистра) среди неудалённых или создать.

    Возвращает (venue, created). Если точка уже была — обновляет timezone и
    default_language на переданные значения: это конфигурация, не история,
    перезаписывать безопасно (в отличие от персонала, см. docstring модуля).

    Сравнение регистра — в Python (str.casefold()), а не через SQL lower():
    lower() в SQLite фолдит только ASCII (кириллица не сворачивается), а в
    Postgres результат зависит от локали сервера. Точек на пилоте — единицы,
    выбрать все неудалённые и сравнить в Python дешевле, чем полагаться на
    диалект-зависимое поведение lower() в БД.
    """
    candidates = (
        await session.execute(select(Venue).where(Venue.deleted_at.is_(None)))
    ).scalars().all()
    existing = next((v for v in candidates if v.name.casefold() == name.casefold()), None)
    if existing is not None:
        existing.timezone = timezone
        existing.default_language = default_language
        await session.flush()
        return existing, False

    venue = Venue(name=name, timezone=timezone, default_language=default_language)
    session.add(venue)
    await session.flush()
    await session.refresh(venue)
    return venue, True


async def ensure_comm_groups(session: AsyncSession, venue: Venue) -> dict[Group, CommGroup]:
    """Завести все 4 группы связи точки (зал/кухня/бар/все), не плодя дублей.

    Имена групп — ровно значения app.domain.intents.Group: это те же строки,
    по которым голосовая маршрутизация ищет адресата ("скажи кухне"), сверка
    со случайными строками сломала бы связь молча.
    """
    groups: dict[Group, CommGroup] = {}
    for group in Group:
        existing = (
            await session.execute(
                select(CommGroup).where(
                    CommGroup.venue_id == venue.id,
                    CommGroup.name == group.value,
                    CommGroup.deleted_at.is_(None),
                )
            )
        ).scalars().first()
        if existing is None:
            existing = CommGroup(venue_id=venue.id, name=group.value)
            session.add(existing)
            await session.flush()
            await session.refresh(existing)
        groups[group] = existing
    return groups


async def _find_active_employee(
    session: AsyncSession, venue_id: int, name: str
) -> Employee | None:
    return (
        await session.execute(
            select(Employee).where(
                Employee.venue_id == venue_id,
                Employee.name == name,
                Employee.deleted_at.is_(None),
            )
        )
    ).scalars().first()


async def _assign_groups(
    session: AsyncSession, employee: Employee, groups: list[CommGroup]
) -> None:
    for group in groups:
        existing = (
            await session.execute(
                select(EmployeeCommGroup).where(
                    EmployeeCommGroup.employee_id == employee.id,
                    EmployeeCommGroup.comm_group_id == group.id,
                )
            )
        ).scalars().first()
        if existing is None:
            session.add(EmployeeCommGroup(employee_id=employee.id, comm_group_id=group.id))
    await session.flush()


@dataclass(frozen=True)
class CreatedStaffEntry:
    """Свежесозданный сотрудник — PIN здесь виден единственный раз, для печати."""

    name: str
    role: str
    language: str
    pin: str
    # Кличка попадает в распечатку не для красоты: смена должна знать, как
    # окликать друг друга голосом, иначе адресация останется неиспользованной.
    nickname: str | None = None
    email: str | None = None
    # Пароль виден единственный раз — здесь. В базе только argon2id-хеш.
    password: str | None = None


@dataclass(frozen=True)
class VenueSeedResult:
    venue: Venue
    venue_created: bool
    groups: dict[Group, CommGroup]
    created_staff: list[CreatedStaffEntry]
    skipped_staff: list[str]


async def seed_venue(session: AsyncSession, config: VenueSeedConfig) -> VenueSeedResult:
    """Завести точку под ключ: venue, 4 группы связи, персонал с PIN.

    Не коммитит сессию — коммит и обработка ошибок остаются на вызывающем
    коде (CLI открывает транзакцию, тест — использует свою сессию/rollback).
    """
    venue, venue_created = await ensure_venue(
        session,
        name=config.venue_name,
        timezone=config.timezone,
        default_language=config.default_language,
    )
    groups = await ensure_comm_groups(session, venue)

    to_create: list[StaffSpec] = []
    skipped: list[str] = []
    for spec in config.staff:
        if await _find_active_employee(session, venue.id, spec.name) is not None:
            skipped.append(spec.name)
        else:
            to_create.append(spec)

    pins = generate_unique_pins(len(to_create))
    # Пароли для тех, у кого есть почта. Как и PIN, показываются один раз.
    passwords = [generate_password() for _ in to_create]
    created: list[CreatedStaffEntry] = []
    for spec, pin, password in zip(to_create, pins, passwords, strict=True):
        employee = Employee(
            venue_id=venue.id,
            name=spec.name,
            nickname=spec.nickname,
            role=spec.role,
            language=spec.language,
            pin_hash=hash_pin(pin),
            email=spec.email,
            password_hash=hash_password(password) if spec.email else None,
        )
        session.add(employee)
        await session.flush()
        await session.refresh(employee)

        target_groups = [groups[g] for g in ROLE_GROUPS[spec.role]]
        await _assign_groups(session, employee, target_groups)

        created.append(
            CreatedStaffEntry(
                name=spec.name,
                role=spec.role,
                language=spec.language,
                pin=pin,
                nickname=spec.nickname,
                email=spec.email,
                password=password if spec.email else None,
            )
        )

    return VenueSeedResult(
        venue=venue,
        venue_created=venue_created,
        groups=groups,
        created_staff=created,
        skipped_staff=skipped,
    )


def format_pin_roster(result: VenueSeedResult) -> str:
    """Список «имя — роль — язык — PIN» для печати и раздачи на смене.

    PIN виден только сейчас, в момент вызова — в БД лежит только argon2id-хеш,
    повторно узнать PIN нельзя (только сбросить и выдать новый).
    """
    lines: list[str] = []
    if not result.created_staff:
        lines.append("Новых сотрудников не создано (все уже были заведены раньше).")
    else:
        lines.append("ДОСТУПЫ ДЛЯ ПЕРВОЙ СМЕНЫ — раздать лично, не пересылать в общий чат.")
        lines.append("")
        header = f"{'Имя':<22} {'Кличка':<12} {'Роль':<10} {'Язык':<6} PIN"
        lines.append(header)
        lines.append("-" * len(header))
        for entry in result.created_staff:
            кличка = entry.nickname or "—"
            lines.append(
                f"{entry.name:<22} {кличка:<12} {entry.role:<10} "
                f"{entry.language:<6} {entry.pin}"
            )

        # Почта и пароль — отдельным блоком: они есть не у всех, и в общей
        # таблице длинный пароль сломал бы колонки.
        с_почтой = [e for e in result.created_staff if e.email]
        if с_почтой:
            lines.append("")
            lines.append("ВХОД ПО ПОЧТЕ (пароль показывается один раз, в базе только хеш):")
            for entry in с_почтой:
                lines.append(f"  {entry.name}")
                lines.append(f"    почта:  {entry.email}")
                lines.append(f"    пароль: {entry.password}")

    if result.skipped_staff:
        lines.append("")
        lines.append(
            "Уже были заведены раньше (пропущены, PIN не менялся): "
            + ", ".join(result.skipped_staff)
        )

    return "\n".join(lines)
