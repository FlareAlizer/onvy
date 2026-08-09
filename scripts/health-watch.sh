#!/usr/bin/env bash
# Одна проверка /health и сигнал в телеграм, когда состояние изменилось.
#
# Сообщение шлётся только на ПЕРЕХОДЕ: упало → одно сообщение, поднялось → одно
# сообщение с длительностью простоя. Иначе ночная авария к утру даёт две сотни
# уведомлений, их выключают, и следующую аварию никто не замечает.
#
# Где запускать — важнее, чем как часто:
#   * Снаружи (GitHub Actions, любая другая машина) — ловит и падение
#     приложения, и смерть всего сервера. Это то, ради чего всё затевалось.
#   * На самом сервере — ловит ТОЛЬКО падение приложения. Если умрёт сервер или
#     отвалится сеть, проверка умрёт вместе с ним и не отправит ничего. Как
#     единственный слой не годится.
#
# Переменные окружения:
#   HEALTH_URL           обязательна, например https://onvy.space/health
#   TELEGRAM_BOT_TOKEN   обязательна (создать бота у @BotFather)
#   TELEGRAM_CHAT_ID     обязательна (свой id — у @userinfobot, или id группы)
#   STATE_FILE           где помнить прошлое состояние (по умолчанию /var/lib/onvy/health.state)
#   TIMEOUT_SECONDS      сколько ждём ответ (по умолчанию 10)
#   TELEGRAM_API_BASE    адрес api телеграма; подменяется только в тестах,
#                        чтобы проверять отправку, не дёргая настоящего бота
set -euo pipefail

HEALTH_URL="${HEALTH_URL:?Не задан HEALTH_URL}"
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:?Не задан TELEGRAM_BOT_TOKEN}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:?Не задан TELEGRAM_CHAT_ID}"
STATE_FILE="${STATE_FILE:-/var/lib/onvy/health.state}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-10}"
TELEGRAM_API_BASE="${TELEGRAM_API_BASE:-https://api.telegram.org}"

mkdir -p "$(dirname "$STATE_FILE")"

# --- Проба ------------------------------------------------------------------
# Две попытки: одиночный обрыв на пути к серверу — это не авария, а сеть. Будить
# человека из-за него нельзя, иначе сигналу перестанут верить.
probe() {
  local body http
  for attempt in 1 2; do
    if body="$(curl -fsS --max-time "$TIMEOUT_SECONDS" "$HEALTH_URL" 2>/dev/null)"; then
      # 200 мало: приложение может отвечать, когда речевой стек уже лёг.
      if printf '%s' "$body" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'; then
        return 0
      fi
      REASON="ответил, но не ok: $(printf '%s' "$body" | head -c 200)"
      [ "$attempt" -eq 2 ] && return 1
    else
      http="$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT_SECONDS" "$HEALTH_URL" 2>/dev/null || true)"
      REASON=$([ "$http" = "000" ] && echo "не отвечает совсем (нет соединения или таймаут)" || echo "HTTP $http")
      [ "$attempt" -eq 2 ] && return 1
    fi
    sleep 3
  done
  return 1
}

REASON=""
if probe; then
  NOW_STATE=up
else
  NOW_STATE=down
fi

# --- Прошлое состояние ------------------------------------------------------
PREV_STATE=up
PREV_SINCE=0
if [ -f "$STATE_FILE" ]; then
  # shellcheck disable=SC1090
  . "$STATE_FILE" 2>/dev/null || true
  PREV_STATE="${STATE:-up}"
  PREV_SINCE="${SINCE:-0}"
fi

NOW_TS="$(date -u +%s)"

send() {
  # Токен в аргументах не печатаем: скрипт часто гоняют с set -x при отладке.
  curl -fsS --max-time 15 \
    "${TELEGRAM_API_BASE}/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
    --data-urlencode "disable_web_page_preview=true" \
    --data-urlencode "text=$1" >/dev/null
}

human_duration() {
  local s=$1 h m
  h=$(( s / 3600 )); m=$(( (s % 3600) / 60 ))
  if [ "$h" -gt 0 ]; then echo "${h} ч ${m} мин"; else echo "${m} мин"; fi
}

WHEN="$(date -u '+%Y-%m-%d %H:%M UTC')"

if [ "$NOW_STATE" = down ] && [ "$PREV_STATE" != down ]; then
  echo "УПАЛО: $REASON"
  send "Onvy не отвечает
$HEALTH_URL
$REASON
$WHEN

Смена сейчас без рации и без ассистента."
  printf 'STATE=down\nSINCE=%s\n' "$NOW_TS" > "$STATE_FILE"
  exit 1
fi

if [ "$NOW_STATE" = up ] && [ "$PREV_STATE" = down ]; then
  DOWN_FOR="$(human_duration $(( NOW_TS - PREV_SINCE )))"
  echo "ПОДНЯЛОСЬ после $DOWN_FOR"
  send "Onvy снова отвечает
$HEALTH_URL
Не работал: $DOWN_FOR
$WHEN"
  printf 'STATE=up\nSINCE=%s\n' "$NOW_TS" > "$STATE_FILE"
  exit 0
fi

# Состояние не изменилось — молчим. Это самый частый исход, и он не должен
# ни писать в телеграм, ни шуметь в журнале.
if [ "$NOW_STATE" = down ]; then
  echo "всё ещё лежит: $REASON"
  exit 1
fi
echo "ok"
