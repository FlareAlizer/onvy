#!/usr/bin/env bash
# Ежедневный дамп Postgres с ротацией.
#
# На сервере запускается таймером systemd, а не вручную и не из cron:
#   bash scripts/install-backup-timer.sh   (ставится один раз)
#   systemctl status onvy-backup.timer
# Таймер сразу после дампа прогоняет scripts/restore-check.sh — сам по себе
# созданный файл ничего не гарантирует, пока из него не поднялась база.
#
# Восстановление — см. docs/runbook-deploy.md ("Бэкап Postgres").
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

COMPOSE="docker compose -f deploy/docker-compose.yml --env-file .env"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/onvy}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
TIMESTAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
FILE="$BACKUP_DIR/onvy-$TIMESTAMP.sql.gz"

if [ ! -f .env ]; then
  echo "Нет .env в корне репозитория — не знаю POSTGRES_USER/DB." >&2
  exit 1
fi
set -a; source .env; set +a

mkdir -p "$BACKUP_DIR"

# PG_CONTAINER можно задать снаружи: на сервере база поднята через compose, а на
# машине разработки — обычным docker run, и compose про неё ничего не знает.
PG_CONTAINER="${PG_CONTAINER:-$($COMPOSE ps -q postgres 2>/dev/null || true)}"
if [ -z "$PG_CONTAINER" ]; then
  echo "Контейнер postgres не найден. Задайте PG_CONTAINER, если база не под compose." >&2
  exit 1
fi

echo "==> Дамп ${POSTGRES_DB:-onvy} -> $FILE"
docker exec -e PGPASSWORD="${POSTGRES_PASSWORD:-}" "$PG_CONTAINER" \
  pg_dump -U "${POSTGRES_USER:-onvy}" -d "${POSTGRES_DB:-onvy}" \
  --format=plain --no-owner --no-privileges | gzip -9 > "$FILE"

# Дамп нулевого размера = дамп провалился молча — не оставляем битый файл вместо бэкапа.
if [ ! -s "$FILE" ]; then
  echo "Дамп пустой — что-то пошло не так, удаляю $FILE" >&2
  rm -f "$FILE"
  exit 1
fi

# Обрыв на середине даёт непустой, но нечитаемый архив. Проверяем сразу: битый
# файл, пролежавший в каталоге две недели, — это бэкап, которого нет.
if ! gzip -t "$FILE" 2>/dev/null; then
  echo "Архив побит (gzip -t не прошёл), удаляю $FILE" >&2
  rm -f "$FILE"
  exit 1
fi

echo "==> OK: $(du -h "$FILE" | cut -f1)"

echo "==> Ротация: удаляю дампы старше $RETENTION_DAYS дней из $BACKUP_DIR"
find "$BACKUP_DIR" -name 'onvy-*.sql.gz' -mtime "+$RETENTION_DAYS" -print -delete
