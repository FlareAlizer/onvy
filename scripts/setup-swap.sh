#!/usr/bin/env bash
#
# Файл подкачки на боевом сервере.
#
# Зачем. 30 июля сборка docker-образа на работающем сервере (4 ядра, 8 ГБ)
# исчерпала память: машина отвечала на ping, порты принимали соединения, но ни
# один процесс не мог ответить — даже sshd на приветствие. Помогла только
# жёсткая перезагрузка из панели провайдера.
#
# Подкачка не заменяет правильное решение (образ теперь собирает CI, см.
# .github/workflows/ci.yml), но не даёт системе встать насмерть: при пиковой
# нагрузке она начнёт тормозить вместо того, чтобы перестать отвечать.
# Разница между «медленно» и «нужна перезагрузка» здесь принципиальна.
#
# Размер 4 ГБ при 8 ГБ памяти: хватает пережить пик, не съедая много диска
# (79 ГБ всего). swappiness=10 — подкачку используем как страховку, а не как
# продолжение памяти: без этого база начнёт вытесняться на диск и всё замедлится.
set -euo pipefail

SWAPFILE=/swapfile
SIZE_GB=4

if swapon --show | grep -q "$SWAPFILE"; then
  echo "Подкачка уже включена:"
  swapon --show
  free -h
  exit 0
fi

echo "==> Создаю файл подкачки ${SIZE_GB} ГБ"
# fallocate быстрее dd и не читает нули с диска.
fallocate -l "${SIZE_GB}G" "$SWAPFILE" 2>/dev/null || \
  dd if=/dev/zero of="$SWAPFILE" bs=1M count=$((SIZE_GB * 1024)) status=none

chmod 600 "$SWAPFILE"
mkswap "$SWAPFILE" >/dev/null
swapon "$SWAPFILE"

# Переживает перезагрузку.
if ! grep -q "^${SWAPFILE}" /etc/fstab; then
  echo "${SWAPFILE} none swap sw 0 0" >> /etc/fstab
  echo "==> Добавлено в /etc/fstab — включится после перезагрузки"
fi

# Подкачка как страховка, а не как замена памяти: при значении по умолчанию (60)
# ядро охотно вытесняет на диск даже когда память есть, и база начинает тормозить.
sysctl -w vm.swappiness=10 >/dev/null
if ! grep -q "vm.swappiness" /etc/sysctl.conf; then
  echo "vm.swappiness=10" >> /etc/sysctl.conf
fi

echo "==> Готово"
swapon --show
free -h
echo "==> Диск:"
df -h / | tail -1
