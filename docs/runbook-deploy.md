# Runbook: развёртывание Onvy на VPS

Пошагово — для человека, который поднимает сервер с нуля вечером 30 июля.
Все команды — для Ubuntu 22.04/24.04 на VPS (Selectel/Timeweb/reg.ru).

## 0. Перед тем как начать

- Домен для пилота уже должен резолвиться A/AAAA-записью на IP этого сервера.
  Без этого Caddy не выпустит TLS-сертификат (Let's Encrypt HTTP-01 ходит по домену).
- Открыт SSH-доступ на сервер, есть права sudo.
- Есть значения для `.env`: `SECRET_KEY`, пароль Postgres, `YANDEX_API_KEY`,
  `YANDEX_FOLDER_ID`, домен.

## 1. Подготовка сервера (один раз)

```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y ca-certificates curl git ufw

# Docker Engine + Compose plugin (официальный скрипт Docker)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
# перелогиниться, чтобы группа docker подхватилась:
newgrp docker

# Файрвол: только SSH, HTTP, HTTPS. Postgres/Redis наружу НЕ публикуются —
# они и не должны (в deploy/docker-compose.yml портов у них наружу нет).
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp   # HTTP/3 у Caddy
sudo ufw --force enable
sudo ufw status
```

Проверить: `docker --version`, `docker compose version`.

## 2. Клонирование и конфигурация

```bash
sudo mkdir -p /opt/onvy && sudo chown "$USER":"$USER" /opt/onvy
git clone <URL_РЕПОЗИТОРИЯ> /opt/onvy
cd /opt/onvy

cp deploy/.env.example .env
nano .env   # заполнить SECRET_KEY, JWT_SECRET, POSTGRES_PASSWORD, DATABASE_URL,
            # YANDEX_API_KEY, YANDEX_FOLDER_ID, DOMAIN, CADDY_EMAIL
```

Генерация секретов:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # JWT_SECRET
openssl rand -base64 24                                          # POSTGRES_PASSWORD
```

`DATABASE_URL` должен использовать те же `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB`,
что заданы чуть выше в том же `.env` — они не связаны автоматически.

## 3. Первый запуск

```bash
cd /opt/onvy

# Собрать образ api (тянет зависимости из uv.lock, собирает фронт из frontend/)
docker compose -f deploy/docker-compose.yml --env-file .env build api

# Поднять БД и Redis, дождаться healthy
docker compose -f deploy/docker-compose.yml --env-file .env up -d postgres redis
docker compose -f deploy/docker-compose.yml --env-file .env ps
# Статус postgres/redis должен стать "healthy" за 10-30 секунд.

# Накатить миграции (ОДИН РАЗ, отдельным шагом — не часть старта api)
docker compose -f deploy/docker-compose.yml --env-file .env --profile tools run --rm migrate

# Поднять api
docker compose -f deploy/docker-compose.yml --env-file .env up -d api
docker compose -f deploy/docker-compose.yml --env-file .env ps   # api -> healthy

# Поднять Caddy — с этого момента должен начаться выпуск TLS-сертификата
docker compose -f deploy/docker-compose.yml --env-file .env up -d caddy
docker compose -f deploy/docker-compose.yml --env-file .env logs -f caddy
# Ищи в логах "certificate obtained successfully" — это подтверждение TLS.
```

Проверка снаружи:

```bash
curl -fsS https://<ВАШ_ДОМЕН>/health
# {"status":"ok","yandex":"on"}
```

Дальше все обновления — через `bash scripts/deploy.sh` (см. ниже), не руками.

## 4. Обычный деплой (после первого раза)

```bash
cd /opt/onvy
bash scripts/deploy.sh
```

Скрипт сам: `git pull` → сборка нового образа `api` → ждёт postgres/redis healthy →
прогоняет `alembic upgrade head` → **только если миграция прошла** — перезапускает
`api` на новом образе → ждёт health-check → поднимает `caddy`. Если что-то падает —
останавливается, ничего не переключает молча.

## 5. Логи

```bash
docker compose -f deploy/docker-compose.yml --env-file .env logs -f api
docker compose -f deploy/docker-compose.yml --env-file .env logs -f caddy
docker compose -f deploy/docker-compose.yml --env-file .env logs -f postgres
docker compose -f deploy/docker-compose.yml --env-file .env logs --tail=200 api   # без follow
```

## 6. Если api не поднялся

1. Смотри логи: `docker compose ... logs --tail=200 api`.
2. Частые причины:
   - `.env` неполный/с опечаткой (проверь `DATABASE_URL`, `SECRET_KEY`) — приложение
     осознанно падает на старте при невалидном конфиге (pydantic-settings).
   - Миграции не накатаны (`alembic upgrade head` не запускался) — схема БД пустая.
   - `postgres`/`redis` не healthy — `docker compose ps`, `docker compose logs postgres`.
3. Health-check самого контейнера: `docker inspect --format='{{json .State.Health}}' <container_id> | jq`.
4. Если правка в `.env` — `docker compose -f deploy/docker-compose.yml --env-file .env up -d api`
   (пересоздаст контейнер с новым env, образ пересобирать не нужно).

## 7. Откат (rollback)

`scripts/deploy.sh` перед сборкой нового образа тегирует текущий как `onvy-api:rollback`.
Откат вручную:

```bash
docker tag onvy-api:rollback onvy-api:latest
docker compose -f deploy/docker-compose.yml --env-file .env up -d api
```

**Важно:** если проблема пришла вместе с миграцией схемы, откат образа не откатывает
БД — миграции в этом проекте пишутся обратимыми (`downgrade()`), при необходимости
откатить схему: `docker compose ... --profile tools run --rm migrate alembic downgrade -1`
(смотри в `alembic/versions/`, какая ревизия предыдущая, если `-1` не подходит).

## 8. Бэкап Postgres

Ставится один раз, из-под root:

```bash
cd /opt/onvy && sudo bash scripts/install-backup-timer.sh
```

Скрипт кладёт юниты из `deploy/systemd/` в `/etc/systemd/system` (подставляя
реальный путь репозитория) и включает таймер. Дальше каждую ночь в 03:20 UTC
(06:20 МСК — смена уже закрылась) выполняется два шага подряд:

1. `scripts/backup-postgres.sh` — дамп с ротацией;
2. `scripts/restore-check.sh` — дамп разворачивается во временную базу и
   проверяется. Если он не восстанавливается, падает весь юнит.

Второй шаг здесь не формальность. Дамп, который никто не пробовал развернуть, —
это файл, а не бэкап: он может быть обрезан на середине, снят до миграции или
вообще не с той базы, и всё это выглядит как нормальный `.sql.gz` в каталоге.

**Таймер, а не cron:** systemd пишет в журнал, показывает статус последнего
запуска и с `Persistent=true` догоняет пропущенный, если сервер в это время был
выключен. У cron нет ни первого, ни второго, ни третьего.

Первый запуск сделать руками, не дожидаясь ночи — расписание, которое ни разу не
отработало, это намерение, а не бэкап:

```bash
systemctl start onvy-backup.service
journalctl -u onvy-backup.service -n 40 --no-pager
ls -lh /var/backups/onvy
```

Проверить расписание и результат последнего запуска:

```bash
systemctl list-timers onvy-backup.timer
systemctl status onvy-backup.service
```

По умолчанию хранит 14 дней в `/var/backups/onvy` (переопределяется переменными
`BACKUP_DIR`, `RETENTION_DAYS`). Проверка восстановления создаёт рядом временную
базу на время прогона и удаляет её в конце — на пиковый момент нужно место
примерно в размер базы.

### Проверить бэкап отдельно

```bash
cd /opt/onvy
bash scripts/restore-check.sh                      # самый свежий дамп
bash scripts/restore-check.sh /var/backups/onvy/onvy-2026-08-04T03-20-00Z.sql.gz
```

Боевую базу скрипт не трогает: он только читает из неё список таблиц, чтобы
сверить с восстановленным.

### Восстановление из бэкапа

Это уже про инцидент — перезапись боевой базы. Проверка выше нужна как раз для
того, чтобы в этот момент не выяснять, рабочий ли файл.

```bash
cd /opt/onvy
FILE=/var/backups/onvy/onvy-<нужная-дата>.sql.gz

# Останавливаем api, чтобы никто не писал в БД во время восстановления
docker compose -f deploy/docker-compose.yml --env-file .env stop api

# Восстанавливаем поверх текущей БД (осторожно — это перезаписывает данные)
set -a; source .env; set +a
gunzip -c "$FILE" | docker exec -i "$(docker compose -f deploy/docker-compose.yml --env-file .env ps -q postgres)" \
  psql -U "${POSTGRES_USER:-onvy}" -d "${POSTGRES_DB:-onvy}"

docker compose -f deploy/docker-compose.yml --env-file .env start api
```

Если нужно восстановить в чистую БД (например, на новом сервере) — сначала подними
`postgres` из `docker-compose.yml` пустым, затем тот же `gunzip -c ... | psql ...`
без `stop api`/`start api` (api ещё не запущен).

## 9. TLS и домен

Caddy сам выпускает и продлевает сертификат Let's Encrypt по домену из `DOMAIN` в
`.env`. Если сертификат не выпускается:

- Проверь, что `DOMAIN` действительно резолвится на IP этого сервера: `dig +short <домен>`.
- Проверь, что порты 80 и 443 открыты наружу (`ufw status`, а также в панели
  провайдера — некоторые VPS фильтруют дополнительно).
- Логи: `docker compose ... logs caddy` — там видно причину отказа ACME.

## 10. Смена версии / масштабирование

Один инстанс `api` рассчитан на пилот в одной точке. Если понадобится больше —
поднять `docker compose -f deploy/docker-compose.yml --env-file .env up -d --scale api=N`
и добавить перед Caddy балансировку (Caddy умеет `reverse_proxy` на несколько
адресов — потребует правки `deploy/Caddyfile`, отдельная задача, не в рамках пилота).
