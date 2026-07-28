"""Yandex SpeechKit: распознавание и синтез.

Рабочий адаптер на старте пилота — он не зависит от готовности GPU-ноды.
После разворачивания GigaAM переключается флагом ASR_PROVIDER, код не меняется.

Аудио от браузера приходит сырым LPCM (16 кГц, моно, 16 бит LE) — без перекодирования
и без ffmpeg на сервере.
"""

import httpx

from app.adapters._timing import measure
from app.config import settings
from app.domain.language import Language
from app.ports.speech import (
    SAMPLE_RATE_HERTZ,
    Recognition,
    SpeechUnavailable,
    Synthesis,
)

_STT_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
_TTS_URL = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"

PROVIDER = "yandex"

# Языки, поддержка которых в SpeechKit подтверждена документацией.
_STT_CONFIRMED: frozenset[Language] = frozenset({"ru", "en", "uz", "kk"})
# Киргизский и таджикский в официальном списке распознавания мы не нашли.
# Не объявляем их поддерживаемыми: пусть маршрутизация отдаёт их GigaAM,
# а если выбора нет — попытка будет сделана с честной записью в лог.
_STT_LOCALE: dict[Language, str] = {
    "ru": "ru-RU",
    "en": "en-US",
    "uz": "uz-UZ",
    "kk": "kk-KK",
    "ky": "ky-KG",
    "tg": "tg-TJ",
}

_TTS_CONFIRMED: frozenset[Language] = frozenset({"ru", "en", "uz", "kk"})
_TTS_VOICE: dict[Language, str] = {
    "ru": "alena",
    "en": "john",
    "uz": "nigora",
    "kk": "amira",
    "ky": "alena",  # голоса нет — говорим русским голосом, чем молчим
    "tg": "alena",
}

# Синхронный STT принимает ≤30 сек и ≤1 МБ. 25 сек LPCM 16 кГц = 800 КБ — влезаем.
_CHUNK_BYTES = SAMPLE_RATE_HERTZ * 2 * 25


def _auth() -> dict[str, str]:
    return {"Authorization": f"Api-Key {settings.yandex_api_key}"}


class YandexSpeechRecognition:
    """Речь → текст через SpeechKit."""

    def supports(self, language: Language) -> bool:
        return language in _STT_CONFIRMED

    async def recognize(self, audio_lpcm: bytes, language: Language) -> Recognition:
        with measure() as took:
            text = await self._recognize_all(audio_lpcm, language)
        return Recognition(text=text, language=language, provider=PROVIDER, duration_ms=took.ms)

    async def _recognize_all(self, audio_lpcm: bytes, language: Language) -> str:
        """Распознать целиком, нарезая длинное аудио на куски по 25 секунд."""
        if len(audio_lpcm) <= _CHUNK_BYTES:
            return await self._recognize_chunk(audio_lpcm, language)
        parts: list[str] = []
        for start in range(0, len(audio_lpcm), _CHUNK_BYTES):
            piece = await self._recognize_chunk(audio_lpcm[start : start + _CHUNK_BYTES], language)
            if piece:
                parts.append(piece)
        return " ".join(parts)

    async def _recognize_chunk(self, audio_lpcm: bytes, language: Language) -> str:
        params = {
            "folderId": settings.yandex_folder_id,
            "lang": _STT_LOCALE.get(language, "ru-RU"),
            "format": "lpcm",
            "sampleRateHertz": str(SAMPLE_RATE_HERTZ),
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    _STT_URL, params=params, content=audio_lpcm, headers=_auth()
                )
        except httpx.HTTPError as exc:
            raise SpeechUnavailable(f"SpeechKit недоступен: {exc}", provider=PROVIDER) from exc
        if resp.status_code != 200:
            raise SpeechUnavailable(
                f"SpeechKit STT {resp.status_code}: {resp.text[:200]}", provider=PROVIDER
            )
        return resp.json().get("result", "")


class YandexSpeechSynthesis:
    """Текст → речь через SpeechKit. Отдаём MP3: браузер играет его без плясок."""

    def supports(self, language: Language) -> bool:
        return language in _TTS_CONFIRMED

    async def synthesize(self, text: str, language: Language) -> Synthesis:
        data = {
            "text": text,
            "lang": _STT_LOCALE.get(language, "ru-RU"),
            "voice": _TTS_VOICE.get(language, "alena"),
            "format": "mp3",
            "folderId": settings.yandex_folder_id,
        }
        with measure() as took:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(_TTS_URL, data=data, headers=_auth())
            except httpx.HTTPError as exc:
                raise SpeechUnavailable(f"SpeechKit недоступен: {exc}", provider=PROVIDER) from exc
            if resp.status_code != 200:
                raise SpeechUnavailable(
                    f"SpeechKit TTS {resp.status_code}: {resp.text[:200]}", provider=PROVIDER
                )
            audio = resp.content
        return Synthesis(
            audio=audio, mime_type="audio/mpeg", provider=PROVIDER, duration_ms=took.ms
        )
