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

## 9. Знать о падении раньше заказчика

Проверка живости с сигналом в телеграм: `scripts/health-watch.sh` дёргает
`/health` и пишет в чат **только когда состояние изменилось** — упало и
поднялось. Молчание значит «всё в порядке», поэтому сигнал не превращается в
шум, который перестают читать.

**Главное — где она запускается.** Проверка на самом сервере ловит только
падение приложения: если умрёт сервер или отвалится сеть, она умрёт вместе с
ними и не отправит ничего. Ровно этот случай уже был — сутки недоступности,
и узнали о них не от проверки. Поэтому основной слой вынесен наружу.

### Основной слой: GitHub Actions

`.github/workflows/health.yml` запускается каждые 5 минут на стороне GitHub.
Завести один раз в **Settings → Secrets and variables → Actions**:

| Что | Имя | Значение |
|---|---|---|
| Секрет | `TELEGRAM_BOT_TOKEN` | токен бота от @BotFather |
| Секрет | `TELEGRAM_CHAT_ID` | свой id (узнать у @userinfobot) или id группы |
| Переменная | `HEALTH_URL` | `https://onvy.space/health` |

Проверить, не дожидаясь расписания: вкладка **Actions → Health → Run workflow**.
Хороший прогон заканчивается словом `ok` и ничем не пишет в чат.

**Честно про частоту:** расписание Actions даёт не чаще раза в 5 минут и под
нагрузкой опаздывает ещё на несколько. Раз в минуту, как хотелось, бесплатно
снаружи не получится. Для «узнать раньше, чем позвонят из зала» пяти минут
хватает: официант не звонит через минуту.

### Если нужна минута

Тот же скрипт ставится таймером на **любую другую** машину — не на боевой
сервер, иначе теряется весь смысл:

```bash
HEALTH_URL=https://onvy.space/health \
TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... \
bash scripts/health-watch.sh
```

Скрипт держит состояние в `STATE_FILE` (по умолчанию
`/var/lib/onvy/health.state`) — это он и отличает переход от продолжающейся
аварии.

### Что именно считается падением

- нет соединения или таймаут;
- ответ не 200;
- ответ 200, но в теле нет `"status": "ok"` — приложение может отвечать, когда
  за ним уже ничего не работает.

Одиночный сбой не будит никого: проба повторяется дважды с паузой, и только
второй отказ считается падением.

## 10. TLS и домен

Caddy сам выпускает и продлевает сертификат Let's Encrypt по домену из `DOMAIN` в
`.env`. Если сертификат не выпускается:

- Проверь, что `DOMAIN` действительно резолвится на IP этого сервера: `dig +short <домен>`.
- Проверь, что порты 80 и 443 открыты наружу (`ufw status`, а также в панели
  провайдера — некоторые VPS фильтруют дополнительно).
- Логи: `docker compose ... logs caddy` — там видно причину отказа ACME.

## 11. Смена версии / масштабирование

Один инстанс `api` рассчитан на пилот в одной точке. Если понадобится больше —
поднять `docker compose -f deploy/docker-compose.yml --env-file .env up -d --scale api=N`
и добавить перед Caddy балансировку (Caddy умеет `reverse_proxy` на несколько
адресов — потребует правки `deploy/Caddyfile`, отдельная задача, не в рамках пилота).

## 12. Аудит перед пилотом — 9 августа

Проверено вживую (`ssh root@89.111.163.121`), не предположено:

- **Контейнеры**: api/postgres/redis/caddy healthy, аптайм 9 дней, память
  781Mi/10Gi, диск 8.0G/79G, подкачка 4G не тронута — ресурсов с большим запасом.
- **Миграции**: `alembic current` == `alembic heads` == `d5a1c8b09f32` — схема
  на боевой базе совпадает с кодом миграций.
- **TLS**: сертификат Let's Encrypt действителен до 28 октября 2026, ACME
  renewal info обновляется каждые ~20 минут — автопродление живое.
- **Порты снаружи**: только 22, 80, 443 (`ss -tlnp`, `ufw status` совпадают).
  Postgres/Redis наружу не смотрят — портов у них в `docker-compose.yml` нет.
- **`.env`**: все ключи заданы, `YANDEX_API_KEY`/`YANDEX_FOLDER_ID` не пустые,
  `/health` отдаёт `{"status":"ok",...,"yandex":true}` с `content-type:
  application/json` (проверено заголовком, не только кодом ответа — см. ловушку
  ниже). Несуществующий пут под `/api` честно отдаёт 404 в JSON, SPA-заглушка
  его не перехватывает.
- **Бэкапы**: таймер `onvy-backup.timer` установлен и включён (следующий запуск
  — ежедневно 03:20 UTC), первый прогон сделан руками: дамп 12K создан,
  `restore-check.sh` поднял его во временную базу, схема `d5a1c8b09f32`
  совпала, 16 таблиц, данные на месте (1 точка, 7 сотрудников, 50 позиций
  меню). `journalctl -u onvy-backup.service` — оба шага `status=0/SUCCESS`.

### Найдено и требует действия

**Блокер — на сервере работает образ 6-дневной давности.** CI собрал и
опубликовал новый образ (`ghcr.io/flarealizer/onvy/api:latest`,
digest `sha256:6976bb3c...`, коммит `890779c`, слияние ветки `dasha-dev`)
9 августа. Контейнер `onvy-api-1` на сервере поднят на digest `sha256:5268980c...`
с 3 августа (`docker inspect onvy-api-1` → `Started: 2026-08-03T08:43`).
**Это значит, что все фиксы рации и присутствия, отмеченные в
`docs/plan-pilot.md` как закрытые ✅ (доставка на нескольких устройствах,
присутствие переживает уход с экрана рации), сейчас НЕ работают в бою** —
проверялись в тестовом окружении, а не на том, что реально поднято. Выкатить:

```bash
ssh -i ~/.ssh/onvy_rsa root@89.111.163.121
cd /opt/onvy && bash scripts/deploy-pull.sh
# затем повторить alembic current / alembic heads и ручной прогон рации
```

**Репозиторий на сервере `/opt/onvy` отстал и не может `git pull`.**
`git status` там показывает коммит от 30 июля, а `git fetch origin master`
падает с `fatal: could not read Username for 'https://github.com'` — на
сервере не настроены креды для HTTPS-клона приватного репозитория. Это не
мешает `deploy-pull.sh` (он тянет только Docker-образ из реестра), но
означает, что **любые операционные скрипты** (бэкап, `health-watch.sh`,
`diagnose-network.sh`), которых нет в образе, не попадают на сервер сами —
их придётся переносить руками (`scp`) до тех пор, пока на сервере не заведут
токен для `git pull` или деплой не станет включать явную синхронизацию
`scripts/`. Файлы бэкапа для этого аудита перенесены так же — см. ловушку ниже.

**Ловушка: `scp` с Windows ломает скрипты переносом строк.** Все `.sh`-файлы,
скопированные с локальной машины (`onvy_rsa` под кириллическим профилем
пользователя), приходят на сервер с CRLF и падают на первой же строке
(`set -euo pipefail` → `invalid option name`, потому что shell видит
`pipefail\r`). Проверка: `file script.sh` покажет `CRLF line terminators`.
Лечится на сервере: `sed -i 's/\r$//' script.sh`. Про саму кириллицу в пути
пользователя — `~/.ssh/known_hosts` не резолвится через мангленный путь Git
Bash (`/c/Users/????????????/.ssh/known_hosts` уходит в `\302\353...`) —
указывать `-o UserKnownHostsFile=` и `-i` явно на путь без кириллицы (скопировать
ключ и known_hosts в `/tmp` или ASCII-каталог) либо использовать полный путь
в кавычках и проверять `ssh -vvv`, если получаешь "Host key verification failed"
без предупреждения о смене ключа — само предупреждение тоже может не
показаться из-за того же мангла пути.

**Риск — ротация логов Docker не настроена.** `/etc/docker/daemon.json`
отсутствует, у контейнеров `LogConfig` без `max-size`/`max-file` — логи растут
неограниченно. Caddy уже накопил 30M за 9 дней (в основном шум от ботов-
сканеров интернета, ищущих `.env`/`wp-config.php`/php-шеллы — это НЕ
компрометация, все ответы честные 200 с `index.html` по SPA-контракту или 404
под `/api`). За две недели пилота это не грозит диском (67G свободно), но
голого предохранителя нет. Добавить в `deploy/docker-compose.yml` каждому
сервису:
```yaml
logging:
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"
```
и пересоздать контейнеры (`docker compose ... up -d --force-recreate`).

**Внешний мониторинг живости не заведён.** `.github/workflows/health.yml`
существует и синтаксически рабочий, но `gh secret list` / `gh variable list`
на репозитории пустые — ни `TELEGRAM_BOT_TOKEN`, ни `TELEGRAM_CHAT_ID`, ни
`HEALTH_URL` не заведены, и `gh run list --workflow=health.yml` не находит
вообще ни одного запуска. Сигнала о падении сервиса снаружи сейчас нет.
Завести (см. §9 выше) и прогнать вручную через Actions → Health → Run workflow
до пилота, не после первого инцидента.
