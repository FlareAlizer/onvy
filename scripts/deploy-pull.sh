#!/usr/bin/env bash
#
# Выкат готового образа из реестра. Собирать образ на боевом сервере нельзя:
# 30 июля сборка съела всю память на 8 ГБ и машина перестала отвечать даже по
# SSH — процессы не получали процессорного времени. Теперь собирает CI
# (.github/workflows/ci.yml, задача build-image), а здесь только скачиваем.
#
# Порядок: pull -> миграции -> перезапуск api -> проверка -> откат при провале.
#
# Требует в .env:
#   API_IMAGE=ghcr.io/<владелец>/<репозиторий>/api:latest
# и выполненного один раз `docker login ghcr.io` (образ приватного репозитория).
set -euo pipefail

cd /opt/onvy
COMPOSE="docker compose -f deploy/docker-compose.yml --env-file .env"

# shellcheck disable=SC1091
API_IMAGE=$(grep -E '^API_IMAGE=' .env | cut -d= -f2- || true)
if [ -z "$API_IMAGE" ]; then
  echo "ОСТАНОВКА: в .env нет API_IMAGE — неизвестно, какой образ скачивать." >&2
  echo "Добавьте строку вида API_IMAGE=ghcr.io/владелец/репозиторий/api:latest" >&2
  exit 1
fi

echo "==> Запоминаю текущий образ для отката"
PREV=$(docker image inspect "$API_IMAGE" --format '{{.Id}}' 2>/dev/null || true)
if [ -n "$PREV" ]; then
  docker tag "$PREV" onvy-api:rollback
  echo "    сохранён как onvy-api:rollback"
else
  echo "    прежнего образа нет (первый выкат) — откатывать будет некуда"
fi

echo "==> Скачиваю образ: $API_IMAGE"
if ! $COMPOSE pull api; then
  echo "ОСТАНОВКА: не удалось скачать образ." >&2
  echo "Проверьте: docker login ghcr.io выполнен? образ существует в реестре?" >&2
  exit 1
fi

echo "==> База и Redis"
$COMPOSE up -d postgres redis
for _ in $(seq 1 20); do
  if $COMPOSE ps --format '{{.Service}} {{.Status}}' | grep -q 'postgres.*healthy'; then break; fi
  sleep 3
done

echo "==> Миграции"
if ! $COMPOSE --profile tools run --rm migrate; then
  echo "ОСТАНОВКА: миграции не прошли. api НЕ перезапускаю — старая версия" >&2
  echo "продолжает работать со старой схемой, это безопаснее полумиграции." >&2
  exit 1
fi

echo "==> Перезапускаю api"
$COMPOSE up -d api

echo "==> Жду готовности"
healthy=""
for _ in $(seq 1 25); do
  if $COMPOSE ps --format '{{.Service}} {{.Status}}' | grep -q 'api.*healthy'; then
    healthy="да"
    break
  fi
  sleep 3
done

if [ -z "$healthy" ]; then
  echo "ПРОВАЛ: api не стал healthy." >&2
  $COMPOSE logs --tail 40 api >&2
  if docker image inspect onvy-api:rollback >/dev/null 2>&1; then
    echo "==> Откатываю на прежний образ" >&2
    docker tag onvy-api:rollback "$API_IMAGE"
    $COMPOSE up -d api
    echo "    откат выполнен, проверьте состояние вручную" >&2
  fi
  exit 1
fi

echo "==> Состояние"
$COMPOSE ps --format 'table {{.Service}}\t{{.Status}}'

echo "==> Проверка снаружи"
DOMAIN=$(grep -E '^DOMAIN=' .env | cut -d= -f2- || echo "")
if [ -n "$DOMAIN" ]; then
  curl -sS --max-time 20 "https://$DOMAIN/health" && echo
fi

echo "==> Готово. Место на диске:"
df -h / | tail -1
docker image prune -f >/dev/null 2>&1 || true
