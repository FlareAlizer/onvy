#!/usr/bin/env bash
# Поставить ежедневный бэкап Postgres таймером systemd. Запускается один раз на
# сервере, из-под root:
#
#   cd /opt/onvy && sudo bash scripts/install-backup-timer.sh
#
# Повторный запуск безопасен: юниты перезаписываются, таймер включается заново.
# Скрипт не делает бэкап сам — он только ставит расписание и показывает, как
# проверить, что оно работает.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR=/etc/systemd/system
SRC="$REPO_ROOT/deploy/systemd"

if [ "$(id -u)" -ne 0 ]; then
  echo "Нужны права root: sudo bash scripts/install-backup-timer.sh" >&2
  exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemd не найден. Тогда cron: 20 3 * * * cd $REPO_ROOT && bash scripts/backup-postgres.sh && bash scripts/restore-check.sh" >&2
  exit 1
fi

echo "==> Ставлю юниты в $UNIT_DIR (репозиторий: $REPO_ROOT)"
for unit in onvy-backup.service onvy-backup.timer; do
  # Путь репозитория подставляем на месте — сервер может стоять не в /opt/onvy.
  sed "s#__ONVY_ROOT__#$REPO_ROOT#g" "$SRC/$unit" > "$UNIT_DIR/$unit"
  echo "    $unit"
done

echo "==> Включаю таймер"
systemctl daemon-reload
systemctl enable --now onvy-backup.timer

echo
echo "==> Готово. Ближайший запуск:"
systemctl list-timers onvy-backup.timer --no-pager || true

cat <<EOF

Что дальше:
  # прогнать прямо сейчас, не дожидаясь ночи (сделает дамп и проверит восстановление)
  systemctl start onvy-backup.service

  # что получилось
  journalctl -u onvy-backup.service -n 40 --no-pager
  ls -lh \${BACKUP_DIR:-/var/backups/onvy}

Первый запуск стоит сделать руками прямо сейчас: расписание, которое ни разу не
отработало, — это не бэкап, а намерение.
EOF
