"""Подготовка точки Onvy к пилоту: venue + группы связи + персонал с PIN,
и отдельно — импорт меню из CSV. Выполнять на сервере, где DATABASE_URL
указывает на боевой/предпилотный Postgres (см. docs/runbook-pilot-setup.md).

Запуск:
    uv run python scripts/seed_venue.py setup --config venue.json
    uv run python scripts/seed_venue.py import-menu --venue-id 1 --csv menu.csv [--dry-run]

Формат venue.json и пример меню.csv — в docs/runbook-pilot-setup.md.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Консоль Windows (cp1251) не печатает часть кириллицы в PIN-таблице — форсируем UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Чтобы `app` импортировался при запуске из корня и из папки scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.seed import format_pin_roster, load_venue_seed_config, seed_venue  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.menu import import_menu_csv  # noqa: E402


def build_arg_parser() -> argparse.ArgumentParser:
    """Вынесено отдельной функцией — разбор аргументов проверяется тестами
    без обращения к БД (tests/test_seed.py)."""
    parser = argparse.ArgumentParser(
        prog="seed_venue.py", description="Подготовка точки Onvy к пилоту"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup = subparsers.add_parser(
        "setup", help="Завести точку, 4 группы связи и персонал с PIN"
    )
    setup.add_argument(
        "--config", required=True, type=Path, help="JSON с точкой и списком персонала"
    )

    import_menu = subparsers.add_parser("import-menu", help="Импортировать меню точки из CSV")
    import_menu.add_argument("--venue-id", required=True, type=int, help="id точки (из setup)")
    import_menu.add_argument("--csv", required=True, type=Path, help="Файл меню (UTF-8 или CP1251)")
    import_menu.add_argument(
        "--dry-run",
        action="store_true",
        help="Только показать план (что создастся/обновится/отклонится), не писать в БД",
    )

    return parser


async def _run_setup(args: argparse.Namespace) -> None:
    config = load_venue_seed_config(args.config)
    async with SessionLocal() as session:
        try:
            result = await seed_venue(session, config)
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    action = "создана" if result.venue_created else "уже существовала (найдена по имени)"
    print(f"Точка «{result.venue.name}» (id={result.venue.id}) — {action}.")
    print(f"Группы связи: {', '.join(group.value for group in result.groups)}.")
    print()
    print(format_pin_roster(result))
    print()
    print(f"venue_id для следующих команд (import-menu и т.д.): {result.venue.id}")


async def _run_import_menu(args: argparse.Namespace) -> None:
    raw = args.csv.read_bytes()
    async with SessionLocal() as session:
        try:
            plan = await import_menu_csv(session, args.venue_id, raw, dry_run=args.dry_run)
            if not args.dry_run:
                await session.commit()
        except Exception:
            await session.rollback()
            raise

    mode = "ПЛАН (--dry-run, ничего не записано в БД)" if args.dry_run else "ПРИМЕНЕНО"
    print(f"Импорт меню точки {args.venue_id} — {mode}")
    print(f"  создать:   {len(plan.to_create)}")
    print(f"  обновить:  {len(plan.to_update)}")
    print(f"  отклонено: {len(plan.rejected)}")
    for row in plan.rejected:
        print(f"    строка {row.line_number} ({row.name!r}): {'; '.join(row.errors)}")
    if args.dry_run and (plan.to_create or plan.to_update):
        print("\nПовторите команду без --dry-run, чтобы применить план.")


async def _dispatch(args: argparse.Namespace) -> None:
    if args.command == "setup":
        await _run_setup(args)
    elif args.command == "import-menu":
        await _run_import_menu(args)
    else:  # pragma: no cover — argparse с required=True сюда не пускает
        raise ValueError(f"Неизвестная команда: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    asyncio.run(_dispatch(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
