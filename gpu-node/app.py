"""HTTP-обёртка над GigaAM-Multilingual для GPU-ноды.

Контракт зафиксирован в app/adapters/gigaam/speech.py основного репозитория
(там же — почему именно эта модель, а не GigaAM-v3, которая только русская):

    POST /v1/recognize?lang=uz
        Content-Type: audio/x-pcm;rate=16000
        тело — сырой LPCM 16 кГц моно 16 бит LE
        -> 200 {"text": "..."}  |  4xx/5xx {"detail": "..."}
    GET  /health -> 200 {"status": "ok", "model": "...", "device": "..."}

Модель ai-sage/GigaAM-Multilingual (revision "ctc" по умолчанию — CTC-голова,
220M) грузится ОДИН раз в lifespan-хуке и живёт в памяти процесса; на каждый
запрос заново не грузится — это убило бы бюджет латентности (на распознавание
в пилоте заложено 0.8 с из 2.5 с p95 от кнопки до звука).

У модели нет потокового режима — только сегменты до 25 секунд
(model.transcribe кидает ValueError на более длинных, дальше нужен бы был
transcribe_longform, который мы намеренно не используем — наша сторона режет
аудио по паузе на клиенте и в адаптере, поэтому здесь это ошибка входа, а не
штатный путь). Длина проверяется и на этой стороне тоже, отдельно от клиента.

Инференс — синхронный блокирующий вызов (torch, GPU), поэтому обработчик
уводит его в threadpool через run_in_threadpool: event loop не блокируется,
/health отвечает даже во время инференса. Доступ к самой модели сериализован
явным threading.Lock — карта одна, конкурентные запросы ждут очередь, а не
дерутся за один CUDA-контекст одновременно.

Языки: ru, en, kk, ky, uz — то, что реально умеет Multilingual. Таджикского
нет ни у одной версии GigaAM; на него отвечаем 422 с понятным detail, чтобы
наша сторона (app/adapters/routing.py) молча ушла на облачный запасной
провайдер, а не зависла и не соврала тишиной.
"""

import logging
import os
import tempfile
import threading
import time
import wave
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger("gigaam")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

MODEL_ID = "ai-sage/GigaAM-Multilingual"
# "ctc" (220M) по умолчанию — укладывается в бюджет латентности. "large_ctc"
# (600M) точнее, но медленнее и тяжелее по VRAM; если меняешь — та же ревизия
# должна быть запечена в образ на сборке (см. gpu-node/Dockerfile ARG).
REVISION = os.environ.get("GIGAAM_REVISION", "ctc")

# Multilingual покрывает ровно эти пять. Таджикского нет ни в одной версии
# GigaAM — намеренно исключён, а не забыт.
SUPPORTED_LANGUAGES = frozenset({"ru", "en", "kk", "ky", "uz"})

SAMPLE_RATE = 16_000
SAMPLE_WIDTH_BYTES = 2  # 16-бит LE
MAX_SEGMENT_SECONDS = 25
MAX_SEGMENT_BYTES = SAMPLE_RATE * SAMPLE_WIDTH_BYTES * MAX_SEGMENT_SECONDS

_state: dict[str, Any] = {"model": None, "device": "unknown"}
_inference_lock = threading.Lock()


def _pcm_to_wav_file(pcm: bytes) -> str:
    """Заворачивает сырой LPCM в WAV-файл — model.transcribe() принимает только путь
    к файлу и сама читает его через ffmpeg (см. load_audio в modeling_gigaam.py)."""
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(SAMPLE_WIDTH_BYTES)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return path


def _run_inference(pcm: bytes) -> tuple[str, int]:
    """Блокирующий вызов модели. Выполняется в threadpool (см. вызов ниже)."""
    model = _state["model"]
    if model is None:
        raise RuntimeError("модель ещё не загружена")

    path = _pcm_to_wav_file(pcm)
    try:
        with _inference_lock:
            started = time.perf_counter()
            result = model.transcribe(path)
            took_ms = int((time.perf_counter() - started) * 1000)
        return result.text, took_ms
    finally:
        Path(path).unlink(missing_ok=True)


def _silence_pcm(seconds: float) -> bytes:
    return b"\x00\x00" * int(SAMPLE_RATE * seconds)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    import torch
    from transformers import AutoModel

    logger.info("Загружаю %s@%s...", MODEL_ID, REVISION)
    started = time.perf_counter()
    # HF_HUB_OFFLINE=1 в рантайм-окружении контейнера (см. Dockerfile) — веса
    # запечены в образ на сборке, здесь только чтение локального кэша, без сети.
    model = AutoModel.from_pretrained(MODEL_ID, revision=REVISION, trust_remote_code=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        logger.warning(
            "CUDA недоступна — модель работает на CPU, латентность будет далека от бюджета пилота"
        )
    model = model.to(device).eval()

    _state["model"] = model
    _state["device"] = device
    logger.info(
        "Модель загружена за %.1f с, устройство=%s", time.perf_counter() - started, device
    )

    try:
        _, warmup_ms = await run_in_threadpool(_run_inference, _silence_pcm(1.0))
        logger.info("Прогрев модели выполнен за %d мс", warmup_ms)
    except Exception:
        logger.exception("Прогрев модели не удался — первый реальный запрос будет медленнее")

    yield

    _state["model"] = None


app = FastAPI(title="Onvy GigaAM node", lifespan=lifespan)


@app.get("/health")
def health() -> JSONResponse:
    ready = _state.get("model") is not None
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ok" if ready else "loading",
            "model": f"{MODEL_ID}@{REVISION}",
            "device": _state.get("device", "unknown"),
        },
    )


@app.post("/v1/recognize")
async def recognize(request: Request, lang: str = Query(...)) -> dict:
    if lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Язык '{lang}' не поддерживается GigaAM-Multilingual "
                f"(есть: {', '.join(sorted(SUPPORTED_LANGUAGES))}). "
                "Клиент должен упасть на облачный ASR-провайдер."
            ),
        )

    pcm = await request.body()

    if len(pcm) % SAMPLE_WIDTH_BYTES != 0:
        raise HTTPException(
            status_code=422,
            detail="Длина тела не кратна 2 байтам — это не 16-бит LE PCM",
        )
    if len(pcm) == 0:
        # Тишина/пустой сегмент — не ошибка, просто нечего распознавать.
        return {"text": ""}
    if len(pcm) > MAX_SEGMENT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Сегмент длиннее {MAX_SEGMENT_SECONDS} с ({len(pcm)} байт) — "
                "у модели нет потокового режима, режь на клиенте перед отправкой"
            ),
        )

    try:
        text, inference_ms = await run_in_threadpool(_run_inference, pcm)
    except Exception as exc:
        logger.exception("Инференс упал: lang=%s bytes=%d", lang, len(pcm))
        raise HTTPException(status_code=500, detail=f"Инференс не удался: {exc}") from exc

    # Эти цифры идут в отчёт пилота как доказательство себестоимости on-premise ASR.
    logger.info(
        "recognize lang=%s bytes=%d inference_ms=%d chars=%d",
        lang,
        len(pcm),
        inference_ms,
        len(text),
    )
    return {"text": text}
