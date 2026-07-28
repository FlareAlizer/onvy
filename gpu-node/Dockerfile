# syntax=docker/dockerfile:1
#
# Onvy — GigaAM-Multilingual на GPU-ноде. Отдельный образ от основного API:
# живёт на арендованной GPU-машине, общается с app по HTTP (GIGAAM_URL).
# Собирать и запускать МОЖНО ТОЛЬКО на хосте с NVIDIA GPU + драйвером,
# совместимым с CUDA 12.6, и установленным nvidia-container-toolkit —
# см. docs/runbook-gpu-node.md. Сборка требует сеть (шаг ниже качает веса
# модели с HuggingFace один раз, на этапе build).
#
#   docker build -f gpu-node/Dockerfile -t onvy-gigaam:latest gpu-node
#
# Веса (~850MB, revision "ctc") запекаются В ОБРАЗ на сборке — рестарт
# контейнера никогда не ходит в HuggingFace за весами (HF_HUB_OFFLINE=1
# в рантайме, см. ниже). Если меняешь GIGAAM_REVISION — пересобери образ,
# рантайм-ревизия должна совпадать с той, что запечена.

FROM nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04@sha256:23debbe74125dc84df96df79cff42079b3b15265c27140714fd27b5aa718faa4

ARG GIGAAM_REVISION=ctc

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/opt/hf-cache \
    PATH="/opt/venv/bin:$PATH"

# ffmpeg — GigaAM декодирует и ресемплирует аудио через ffmpeg-субпроцесс
# (см. load_audio в modeling_gigaam.py), это не опционально.
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-venv python3-pip ffmpeg ca-certificates && \
    rm -rf /var/lib/apt/lists/* && \
    python3 -m venv /opt/venv

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Единственный шаг, которому нужна сеть: тянет веса ревизии GIGAAM_REVISION
# в HF_HOME и запекает их слоем образа.
RUN python3 -c "from transformers import AutoModel; \
AutoModel.from_pretrained('ai-sage/GigaAM-Multilingual', revision='${GIGAAM_REVISION}', trust_remote_code=True)"

# С этого момента — никакой сети к HuggingFace, даже случайно при рестарте.
ENV HF_HUB_OFFLINE=1 \
    GIGAAM_REVISION=${GIGAAM_REVISION}

RUN groupadd --gid 10001 gigaam && \
    useradd --uid 10001 --gid gigaam --no-create-home --shell /usr/sbin/nologin gigaam && \
    chown -R gigaam:gigaam /opt/hf-cache

WORKDIR /app
COPY app.py .
RUN chown -R gigaam:gigaam /app
USER gigaam

EXPOSE 8000

# Старт с холодной картой + прогрев модели укладывается в 60с на большинстве
# GPU; если нода слабее — увеличь start_period, не убирай healthcheck.
HEALTHCHECK --interval=15s --timeout=5s --start-period=90s --retries=5 \
    CMD ["python3", "-c", "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else sys.exit(1)"]

CMD ["python3", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
