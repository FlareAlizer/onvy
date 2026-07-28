#!/usr/bin/env bash
# Разворачивает Onvy на сервере. Запускать РУКАМИ с сервера, из корня репозитория:
#   bash scripts/deploy.sh
#
# Порядок: git pull -> build нового образа api -> подождать postgres/redis
# healthy -> прогнать миграции (alembic upgrade head) -> только если миграции
# прошли — перезапустить api по новому образу -> health-check -> caddy up.
#
# Если что-то падает на любом шаге — скрипт останавливается (set -e) и старый
# api-контейнер продолжает работать на старом образе (мы не трогаем его, пока
# не убедимся, что новый готов и миграции применились).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

COMPOSE="docker compose -f deploy/docker-compose.yml --env-file .env"
LOCK_FILE="/tmp/onvy-deploy.lock"

# Не даём двум деплоям запуститься параллельно с одной машины.
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
  echo "Другой деплой уже выполняется ($LOCK_FILE занят). Прерываюсь." >&2
  exit 1
fi

if [ ! -f .env ]; then
  echo "Нет .env в корне репозитория. Скопируй deploy/.env.example -> .env и заполни." >&2
  exit 1
fi

echo "==> Текущий коммит на сервере до деплоя:"
git log -1 --oneline || true

echo "==> git pull"
git pull --ff-only

echo "==> Коммит после pull:"
git log -1 --oneline

# Запоминаем ID сейчас работающего api-образа, чтобы было куда откатиться.
PREV_IMAGE_ID="$($COMPOSE images -q api 2>/dev/null || true)"
if [ -n "$PREV_IMAGE_ID" ]; then
  docker tag "$PREV_IMAGE_ID" onvy-api:rollback
  echo "==> Сохранил текущий образ как onvy-api:rollback ($PREV_IMAGE_ID)"
else
  echo "==> Предыдущего образа api не найдено (первый деплой?) — rollback-тег не создаю."
fi

echo "==> Собираю новый образ api"
$COMPOSE build api

echo "==> Поднимаю postgres/redis, жду healthy"
$COMPOSE up -d postgres redis
for svc in postgres redis; do
  for _ in $(seq 1 30); do
    status="$(docker inspect -f '{{.State.Health.Status}}' "$($COMPOSE ps -q "$svc")" 2>/dev/null || echo "unknown")"
    [ "$status" = "healthy" ] && break
    sleep 2
  done
  if [ "$status" != "healthy" ]; then
    echo "Сервис $svc не стал healthy вовремя. Смотри: docker compose -f deploy/docker-compose.yml logs $svc" >&2
    exit 1
  fi
done

echo "==> Прогоняю миграции (alembic upgrade head)"
if ! $COMPOSE --profile tools run --rm migrate; then
  echo "Миграция не прошла. api НЕ трогаю — старый контейнер продолжает работать." >&2
  echo "Откат образа не нужен (api ещё не обновлялся). Разбирайся с миграцией и повтори." >&2
  exit 1
fi

echo "==> Миграции применены. Перезапускаю api на новом образе"
$COMPOSE up -d api

echo "==> Жду, пока api станет healthy"
ok=false
for _ in $(seq 1 30); do
  status="$(docker inspect -f '{{.State.Health.Status}}' "$($COMPOSE ps -q api)" 2>/dev/null || echo "unknown")"
  if [ "$status" = "healthy" ]; then
    ok=true
    break
  fi
  sleep 2
done

if [ "$ok" != "true" ]; then
  echo "api не стал healthy. Логи:" >&2
  $COMPOSE logs --tail=100 api >&2
  if [ -n "$PREV_IMAGE_ID" ]; then
    echo "==> Откатываю api на предыдущий образ (onvy-api:rollback)" >&2
    docker tag onvy-api:rollback onvy-api:latest
    $COMPOSE up -d api
    echo "Откатил api. Миграции уже применены новой БД-схемой — проверь совместимость руками!" >&2
  fi
  exit 1
fi

echo "==> api healthy. Поднимаю caddy"
$COMPOSE up -d caddy

echo "==> Готово. Проверь: curl -fsS https://\$DOMAIN/health (см. .env)"
