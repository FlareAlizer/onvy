#!/usr/bin/env bash
# Проверка, что дамп действительно восстанавливается.
#
# Непроверенный бэкап — это не бэкап, а файл. Скрипт берёт свежий дамп, заливает
# его во ВРЕМЕННУЮ базу рядом с боевой, сверяет состав таблиц с живой базой и
# удаляет временную. Боевую базу не трогает ни на одном шаге — поэтому проверку
# можно гонять хоть каждую ночь, а не «хотя бы раз до пилота».
#
# Запуск вручную:
#   bash scripts/restore-check.sh                  # проверить самый свежий дамп
#   bash scripts/restore-check.sh /path/dump.sql.gz
#
# В systemd вызывается вторым шагом после backup-postgres.sh — см.
# deploy/systemd/onvy-backup.service и docs/runbook-deploy.md.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

COMPOSE="docker compose -f deploy/docker-compose.yml --env-file .env"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/onvy}"

if [ ! -f .env ]; then
  echo "Нет .env в корне репозитория — не знаю POSTGRES_USER/DB." >&2
  exit 1
fi
set -a; source .env; set +a

PG_USER="${POSTGRES_USER:-onvy}"
PG_DB="${POSTGRES_DB:-onvy}"

# PG_CONTAINER можно задать снаружи: на сервере база поднята через compose, а на
# машине разработки — обычным docker run, и compose про неё ничего не знает.
PG_CONTAINER="${PG_CONTAINER:-$($COMPOSE ps -q postgres 2>/dev/null || true)}"
if [ -z "$PG_CONTAINER" ]; then
  echo "Контейнер postgres не найден. Задайте PG_CONTAINER, если база не под compose." >&2
  exit 1
fi

FILE="${1:-}"
if [ -z "$FILE" ]; then
  # Самый свежий дамп. ls -t по маске, а не find -printf: BusyBox/macOS их не знают.
  FILE="$(ls -t "$BACKUP_DIR"/onvy-*.sql.gz 2>/dev/null | head -n 1 || true)"
fi
if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
  echo "Нечего проверять: в $BACKUP_DIR нет ни одного дампа." >&2
  exit 1
fi

echo "==> Проверяю дамп: $FILE ($(du -h "$FILE" | cut -f1))"

# Битый архив ловим до того, как начнём лить его в базу.
if ! gzip -t "$FILE" 2>/dev/null; then
  echo "ПРОВАЛ: архив побит, gzip не может его прочитать." >&2
  exit 1
fi

CHECK_DB="onvy_restore_check_$$"

psql_admin() {
  docker exec -i -e PGPASSWORD="${POSTGRES_PASSWORD:-}" "$PG_CONTAINER" \
    psql -v ON_ERROR_STOP=1 -U "$PG_USER" -d postgres -tAc "$1"
}
psql_check() {
  docker exec -i -e PGPASSWORD="${POSTGRES_PASSWORD:-}" "$PG_CONTAINER" \
    psql -v ON_ERROR_STOP=1 -U "$PG_USER" -d "$CHECK_DB" -tAc "$1"
}

# Временную базу убираем в любом случае: и когда проверка провалилась, и когда
# скрипт прервали. Иначе на диске копятся копии боевой базы.
cleanup() {
  psql_admin "DROP DATABASE IF EXISTS \"$CHECK_DB\";" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "==> Временная база: $CHECK_DB"
psql_admin "CREATE DATABASE \"$CHECK_DB\" OWNER \"$PG_USER\";" >/dev/null

echo "==> Восстанавливаю"
# ON_ERROR_STOP: без него psql проглотит ошибки и «восстановит» половину дампа,
# а скрипт отрапортует успех — ровно та ложь, ради которой всё это и делается.
if ! gunzip -c "$FILE" | docker exec -i -e PGPASSWORD="${POSTGRES_PASSWORD:-}" "$PG_CONTAINER" \
  psql -v ON_ERROR_STOP=1 -q -U "$PG_USER" -d "$CHECK_DB" >/dev/null; then
  echo "ПРОВАЛ: дамп не восстанавливается." >&2
  exit 1
fi

# --- Что именно считаем восстановленным ------------------------------------

# 1. Версия схемы. Без alembic_version дамп снят мимо приложения.
VERSION="$(psql_check "SELECT version_num FROM alembic_version LIMIT 1;" || true)"
if [ -z "$VERSION" ]; then
  echo "ПРОВАЛ: в восстановленной базе нет версии схемы (alembic_version)." >&2
  exit 1
fi
echo "    версия схемы: $VERSION"

# 2. Состав таблиц совпадает с живой базой. Ловит дамп не той базы и дамп,
#    снятый до миграции, — по одному лишь «файл не пустой» это не видно.
TABLES_LIVE="$(docker exec -i -e PGPASSWORD="${POSTGRES_PASSWORD:-}" "$PG_CONTAINER" \
  psql -tAc "SELECT string_agg(tablename, ',' ORDER BY tablename) FROM pg_tables WHERE schemaname='public';" \
  -U "$PG_USER" -d "$PG_DB")"
TABLES_CHECK="$(psql_check "SELECT string_agg(tablename, ',' ORDER BY tablename) FROM pg_tables WHERE schemaname='public';")"

if [ "$TABLES_LIVE" != "$TABLES_CHECK" ]; then
  echo "ПРОВАЛ: состав таблиц не совпадает с живой базой." >&2
  echo "  живая:        $TABLES_LIVE" >&2
  echo "  из бэкапа:    $TABLES_CHECK" >&2
  exit 1
fi
echo "    таблиц восстановлено: $(echo "$TABLES_CHECK" | tr ',' '\n' | wc -l | tr -d ' ')"

# 3. Данные на месте. Пустая схема без единой строки восстанавливается прекрасно
#    и не стоит ничего — заведение по такому бэкапу не поднять.
ROWS_VENUES="$(psql_check "SELECT count(*) FROM venues;")"
ROWS_EMPLOYEES="$(psql_check "SELECT count(*) FROM employees;")"
ROWS_MENU="$(psql_check "SELECT count(*) FROM menu_items;")"
echo "    точек: $ROWS_VENUES · сотрудников: $ROWS_EMPLOYEES · позиций меню: $ROWS_MENU"

if [ "$ROWS_VENUES" -eq 0 ] || [ "$ROWS_EMPLOYEES" -eq 0 ]; then
  echo "ПРОВАЛ: в бэкапе нет ни точки, ни сотрудников — восстанавливать нечего." >&2
  exit 1
fi

echo "==> OK: бэкап восстанавливается, схема $VERSION, данные на месте."
