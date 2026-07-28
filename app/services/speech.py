"""Реальные ASR и TTS через Yandex SpeechKit.

- ASR (STT): синхронное распознавание короткого аудио (до ~30 сек), формат LPCM
  (сырой 16-bit PCM моно), который отдаёт наш веб-клиент из браузера — без ffmpeg.
- TTS: синтез речи, возвращаем MP3 (браузер играет его без плясок).

Аутентификация — по API-ключу сервисного аккаунта (заголовок Authorization: Api-Key).
Ключ и folder_id — только из .env (см. app/config.py).
"""

import httpx

from app.config import settings

_STT_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
_TTS_URL = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"

# Язык сотрудника (ISO 639-1) → код языка и голос TTS Yandex.
_LANG_TO_STT = {"ru": "ru-RU", "en": "en-US", "uz": "uz-UZ", "kk": "kk-KK", "tr": "tr-TR"}
_LANG_TO_VOICE = {"ru": "alena", "en": "john", "uz": "nigora", "kk": "amira", "tr": "silaerkan"}

# Частота дискретизации PCM, который присылает браузер (см. web/js/recorder.js).
SAMPLE_RATE_HERTZ = 16000


class SpeechError(RuntimeError):
    """Ошибка обращения к SpeechKit (сеть/квоты/некорректное аудио)."""


def _auth_header() -> dict[str, str]:
    return {"Authorization": f"Api-Key {settings.yandex_api_key}"}


async def recognize(audio_lpcm: bytes, language: str = "ru") -> str:
    """Распознать сырой PCM (16 kHz, mono, 16-bit LE) → текст.

    Args:
        audio_lpcm: аудио в формате LPCM (raw PCM без заголовка).
        language: язык говорящего (ISO 639-1).
    Returns:
        Распознанный текст (может быть пустым, если тишина).
    """
    params = {
        "folderId": settings.yandex_folder_id,
        "lang": _LANG_TO_STT.get(language, "ru-RU"),
        "format": "lpcm",
        "sampleRateHertz": str(SAMPLE_RATE_HERTZ),
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            _STT_URL, params=params, content=audio_lpcm, headers=_auth_header()
        )
    if resp.status_code != 200:
        raise SpeechError(f"STT {resp.status_code}: {resp.text}")
    return resp.json().get("result", "")


async def recognize_long(audio_lpcm: bytes, language: str = "ru") -> str:
    """Распознать длинную запись (смена/диалог), нарезая PCM на куски ≤25 сек.

    Синхронный STT Yandex принимает ≤30 сек и ≤1 МБ: 25 сек LPCM 16 kHz mono
    16-bit = 800 КБ — укладываемся. Куски распознаются по очереди и склеиваются.
    """
    chunk_bytes = SAMPLE_RATE_HERTZ * 2 * 25  # 25 секунд PCM (2 байта/сэмпл)
    parts: list[str] = []
    for start in range(0, len(audio_lpcm), chunk_bytes):
        text = await recognize(audio_lpcm[start : start + chunk_bytes], language)
        if text:
            parts.append(text)
    return " ".join(parts)


async def synthesize(text: str, language: str = "ru") -> bytes:
    """Синтезировать речь из текста → MP3-байты.

    Args:
        text: что озвучить.
        language: язык/голос (ISO 639-1).
    Returns:
        Аудио MP3.
    """
    data = {
        "text": text,
        "lang": _LANG_TO_STT.get(language, "ru-RU"),
        "voice": _LANG_TO_VOICE.get(language, "alena"),
        "format": "mp3",
        "folderId": settings.yandex_folder_id,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(_TTS_URL, data=data, headers=_auth_header())
    if resp.status_code != 200:
        raise SpeechError(f"TTS {resp.status_code}: {resp.text}")
    return resp.content
