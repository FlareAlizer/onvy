#!/usr/bin/env bash
#
# Диагностика: почему сервер не отвечает снаружи, хотя контейнеры работают.
#
# Симптом (30 июля): изнутри всё здорово — api/postgres/redis healthy, память
# свободна. Снаружи ни SSH, ни HTTPS: TCP-порт принимает соединение, но обмен
# данными не начинается. Проверено с трёх независимых адресов — недоступен
# для всех, значит дело не в блокировке одного клиента.
#
# Запускать в консоли сервера (VNC в панели провайдера), вывод переслать.
set +e

echo "═══ 1. Слушает ли кто-то порты 22, 80, 443 ═══"
ss -tlnp 2>/dev/null | grep -E ':(22|80|443)\b' || echo "  НИКТО НЕ СЛУШАЕТ — вот и причина"

echo
echo "═══ 2. Отвечает ли приложение локально ═══"
curl -sS -o /dev/null -w "  localhost:8000/health -> %{http_code}\n" --max-time 8 http://127.0.0.1:8000/health
curl -sS -o /dev/null -w "  localhost:80        -> %{http_code}\n" --max-time 8 http://127.0.0.1/ 2>&1 | tail -1

echo
echo "═══ 3. Файрвол ═══"
ufw status verbose 2>/dev/null | head -15 || echo "  ufw не установлен"

echo
echo "═══ 4. Правила блокировки (INPUT) ═══"
iptables -L INPUT -n -v 2>/dev/null | head -15

echo
echo "═══ 5. Не банит ли нас fail2ban ═══"
if command -v fail2ban-client >/dev/null 2>&1; then
  fail2ban-client status 2>/dev/null
  fail2ban-client status sshd 2>/dev/null | grep -iE 'banned|total' || true
else
  echo "  fail2ban не установлен (значит и не он)"
fi

echo
echo "═══ 6. Размер пакета (MTU) ═══"
# Если MTU занижен, TCP-рукопожатие проходит (пакеты крошечные), а первый же
# обмен данными теряется — ровно тот симптом, что мы видим.
ip -o link show | awk '{print "  " $2, $0}' | grep -o 'mtu [0-9]*' | sort -u
ip route get 8.8.8.8 2>/dev/null | head -2

echo
echo "═══ 7. Есть ли интернет с сервера ═══"
curl -sS -o /dev/null -w "  до ya.ru -> %{http_code} за %{time_total}s\n" --max-time 10 https://ya.ru || echo "  ИСХОДЯЩЕГО ИНТЕРНЕТА НЕТ"

echo
echo "═══ 8. Внешний адрес, каким нас видят ═══"
curl -sS --max-time 10 https://api.ipify.org 2>/dev/null && echo || echo "  не удалось узнать"

echo
echo "═══ 9. Свежие отказы в журнале SSH ═══"
journalctl -u ssh --no-pager -n 15 2>/dev/null | tail -15 || \
  tail -15 /var/log/auth.log 2>/dev/null || echo "  журнал недоступен"

echo
echo "═══ Готово. Перешлите вывод целиком. ═══"
