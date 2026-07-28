# Runbook: GPU-нода для GigaAM-Multilingual

Отдельная машина от основного VPS. Общается с основным API по HTTP
(`GIGAAM_URL`), сама наружу в интернет не смотрит — см. раздел «Сеть».

**Не проверено вживую** (нет GPU и Docker в песочнице, где это писалось):
сборка образа, реальная загрузка модели на GPU, инференс, поведение
nvidia-container-toolkit. Проверено без GPU: синтаксис Dockerfile/compose
(YAML), логика HTTP-обёртки (`gpu-node/tests/`, 10 тестов, все зелёные —
валидация языка/длины сегмента/пустого аудио/ошибок модели через заглушку),
`ruff check` без замечаний. Реальную проверку на железе — см. шаг 5 ниже,
пройти её до переключения `ASR_PROVIDER=gigaam` на проде.

## 0. Модель — что именно и почему

`ai-sage/GigaAM-Multilingual`, revision **`ctc`** (220M, CTC-голова, ~850MB
весов). Покрывает `ru, en, kk, ky, uz`. **Не** `GigaAM-v3` — та только
русская. Таджикского нет ни у одной версии GigaAM — сервис отвечает на него
422, дальше основное приложение обязано откатиться на облачный провайдер
(Yandex), не молчать.

Официальная карточка модели и пример использования:
https://huggingface.co/ai-sage/GigaAM-Multilingual

## 1. Аренда ноды

Ориентир по ресёрчу (**перепроверить актуальную цену и наличие перед
оплатой** — рынок GPU-аренды меняется быстро, эти цифры не гарантированы):

- Selectel, RTX 4090 — ориентировочно ~51 800 ₽/мес.
- Friend IT, RTX 4090 — ориентировочно ~44 900 ₽/мес.

Минимум для `ctc`-ревизии: одна RTX 4090 (24GB VRAM с большим запасом на
220M-модель), Ubuntu 22.04/24.04 на хосте, публичный IP только для SSH
(остальное — см. раздел «Сеть»).

## 2. Подготовка хоста: драйвер + nvidia-container-toolkit

```bash
# Драйвер NVIDIA (если провайдер не поставил заранее)
sudo apt-get update
sudo apt-get install -y ubuntu-drivers-common
sudo ubuntu-drivers autoinstall
sudo reboot
# после ребута:
nvidia-smi   # должна показать карту и версию драйвера/CUDA

# Docker Engine, если ещё не стоит
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
newgrp docker

# nvidia-container-toolkit — без него GPU не пробросится в контейнер
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Проверка, что Docker видит GPU:
docker run --rm --gpus all nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04 nvidia-smi
```

Если последняя команда не показывает карту — не идти дальше, разбираться тут
(см. раздел 6). Образ `onvy-gigaam` без рабочего GPU-проброса просто уйдёт на
CPU и будет в 10-20 раз медленнее бюджета латентности.

**Совместимость драйвера с CUDA 12.6.** Образ собран на
`nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04`. Нужен драйвер NVIDIA не
старее той версии, что требует CUDA 12.6 (ориентир — 560.x и новее для
Linux x86_64; `nvidia-smi` в шапке вывода показывает и версию драйвера, и
максимальную поддерживаемую CUDA). Если провайдер даёт более старый драйвер
и обновить нельзя — либо обновить драйвер отдельно, либо пересобрать образ
на более старом теге `nvidia/cuda` под тот драйвер (правка одной строки
`FROM` в `gpu-node/Dockerfile`).

## 3. Развёртывание сервиса

```bash
git clone <URL_РЕПОЗИТОРИЯ> /opt/onvy-gpu
cd /opt/onvy-gpu/gpu-node

cp .env.example .env
nano .env   # GIGAAM_REVISION=ctc, GIGAAM_BIND_HOST — см. раздел «Сеть» ниже,
            # не оставляй его 0.0.0.0 без понимания, что делаешь

# Сборка тянет веса модели (~850MB) с HuggingFace — нужна сеть на этом шаге,
# дальше не нужна вообще (HF_HUB_OFFLINE=1 в рантайме).
docker compose build
docker compose up -d

docker compose logs -f gigaam
# Ищи: "Модель загружена за N.N с, устройство=cuda" — если "устройство=cpu",
# GPU не пробросился, смотри шаг 2.
```

Первый старт медленнее (прогрев модели), последующие рестарты — без сети,
веса уже в образе.

## 4. Проверка, что модель реально отвечает

```bash
# Здоровье
curl -fsS http://127.0.0.1:8000/health
# {"status":"ok","model":"ai-sage/GigaAM-Multilingual@ctc","device":"cuda"}

# Реальное распознавание: нужен сырой LPCM 16кГц моно 16-бит LE.
# Быстрый способ получить такой файл из любого wav через ffmpeg:
ffmpeg -i example.wav -f s16le -ac 1 -ar 16000 -acodec pcm_s16le sample.pcm

time curl -fsS -X POST "http://127.0.0.1:8000/v1/recognize?lang=ru" \
  -H "Content-Type: audio/x-pcm;rate=16000" \
  --data-binary @sample.pcm
# {"text":"..."}
# `time` тут — грубая оценка сквозной латентности вместе с сетевым RTT;
# точная цифра инференса — в логах контейнера (inference_ms=...).

# Неподдержанный язык — ожидаем 422, не 500 и не тишину:
curl -i -X POST "http://127.0.0.1:8000/v1/recognize?lang=tg" \
  -H "Content-Type: audio/x-pcm;rate=16000" \
  --data-binary @sample.pcm
```

Только после того, как это реально отвечает `{"text": "..."}` на живой карте —
переключать прод (шаг 7).

## 5. Замер занятости карты

```bash
nvidia-smi                 # разовый снимок: память, загрузка, температура
watch -n 1 nvidia-smi       # live-обновление раз в секунду
nvidia-smi dmon -s um        # компактный поток метрик (utilization, memory)
```

Цифры инференса (`inference_ms` на каждый запрос) — в логах контейнера:

```bash
docker compose logs -f gigaam | grep recognize
```

Эти цифры идут в отчёт пилота как подтверждение себестоимости on-premise ASR
— не терять, копировать в отчёт по мере накопления.

## 6. Если нода не поднялась

| Симптом | Что проверить |
|---|---|
| `docker run --gpus all ... nvidia-smi` не видит карту | nvidia-container-toolkit не настроен (`nvidia-ctk runtime configure`), Docker не перезапущен после настройки |
| В логах "устройство=cpu" вместо cuda | то же самое, либо драйвер несовместим с CUDA 12.6 образа — см. раздел 2 |
| Контейнер падает при сборке на шаге `AutoModel.from_pretrained` | нет сети на этапе `docker compose build`, либо HuggingFace недоступен из региона — попробуй с VPN/прокси только для build-шага |
| Healthcheck не зеленеет дольше `start_period` (90с) | смотри `docker compose logs gigaam` — модель может грузиться дольше на слабой карте; увеличь `start_period` в `gpu-node/docker-compose.yml`, это не баг, а слишком короткий таймаут |
| CUDA out of memory | ревизия `large_ctc` (600M) не влезла в VRAM карты — вернись на `ctc` (220M), пересобери образ с `GIGAAM_REVISION=ctc` |
| 500 на `/v1/recognize` | `docker compose logs gigaam` — там полный traceback; частая причина — битый/пустой WAV на входе, проверь клиента |

## 7. Переключение основного приложения на GigaAM

На основном VPS, в `.env` (не здесь — это уже `deploy/.env.example` из
основного деплоя):

```bash
ASR_PROVIDER=gigaam
GIGAAM_URL=http://<адрес-GPU-ноды-в-приватной-сети>:8000
```

Дальше — обычный `bash scripts/deploy.sh` на основном VPS (перечитывает
`.env`, перезапускает `api`). Откат — тем же `.env` вернуть `ASR_PROVIDER=yandex`
и передеплоить; GigaAM-нода при этом продолжает работать, просто перестаёт
получать трафик.

**Деградация уже встроена в адаптер** (`app/adapters/gigaam/speech.py`):
если нода недоступна или отвечает не 200 — основное приложение уходит в
честную деградацию («ассистент сейчас недоступен»), а не роняет рацию.
Специально проверять это здесь не нужно, только не забывать: неподнятая
GPU-нода не блокирует пилот, просто ASR остаётся на Yandex.

## 8. Сеть — обязательно прочитать перед первым запуском

Сервис **без авторизации** — кто угодно, кто может достучаться до порта 8000,
может гонять через него аудио и получать транскрипцию бесплатно за счёт вашей
аренды. Наружу (публичный интернет) он выставляться не должен ни при каких
обстоятельствах.

Рекомендуемая схема — WireGuard между GPU-нодой и основным VPS:

```bash
# На обеих машинах:
sudo apt-get install -y wireguard
wg genkey | tee privatekey | wg pubkey > publickey
# Обменяться публичными ключами, поднять интерфейс wg0 с приватными IP
# (например, VPS — 10.8.0.1, GPU-нода — 10.8.0.2). Дальше:

# В gpu-node/.env на GPU-ноде:
GIGAAM_BIND_HOST=10.8.0.2   # приватный IP этой ноды в WireGuard-сети

# В .env основного API на VPS:
GIGAAM_URL=http://10.8.0.2:8000

# Файрвол на GPU-ноде — доп. слой защиты поверх bind-адреса, на случай
# опечатки в GIGAAM_BIND_HOST:
sudo ufw allow from 10.8.0.1 to any port 8000 proto tcp
sudo ufw allow OpenSSH
sudo ufw --force enable
```

Если WireGuard не успевается до 31.07 и провайдер даёт приватную сеть между
своими же машинами (VLAN/VPC) — использовать её вместо WireGuard, логика та
же: `GIGAAM_BIND_HOST` = приватный IP ноды в этой сети, `GIGAAM_URL` на
стороне API = тот же адрес, порт 8000 не должен быть достижим с публичного
интернета ни при каком раскладе.
