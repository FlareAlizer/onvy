#!/usr/bin/env bash
# Ежедневный дамп Postgres с ротацией. Ставится в cron на сервере:
#   0 3 * * * cd /opt/onvy && bash scripts/backup-postgres.sh >> /var/log/onvy-backup.log 2>&1
#
# Восстановление — см. docs/runbook-deploy.md ("Восстановление из бэкапа").
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

PG_CONTAINER="$($COMPOSE ps -q postgres)"
if [ -z "$PG_CONTAINER" ]; then
  echo "Контейнер postgres не запущен." >&2
  exit 1
fi

echo "==> Дамп ${POSTGRES_DB:-onvy} -> $FILE"
docker exec "$PG_CONTAINER" pg_dump -U "${POSTGRES_USER:-onvy}" -d "${POSTGRES_DB:-onvy}" \
  --format=plain --no-owner --no-privileges | gzip -9 > "$FILE"

# Дамп нулевого размера = дамп провалился молча — не оставляем битый файл вместо бэкапа.
if [ ! -s "$FILE" ]; then
  echo "Дамп пустой — что-то пошло не так, удаляю $FILE" >&2
  rm -f "$FILE"
  exit 1
fi

echo "==> OK: $(du -h "$FILE" | cut -f1)"

echo "==> Ротация: удаляю дампы старше $RETENTION_DAYS дней из $BACKUP_DIR"
find "$BACKUP_DIR" -name 'onvy-*.sql.gz' -mtime "+$RETENTION_DAYS" -print -delete
