"""GigaAM на своей GPU-ноде — целевой ASR продукта.

Экономика Onvy держится на этом адаптере: облачное распознавание съедало ~2 300 ₽
на сотрудника в месяц (74% себестоимости), своя нода уводит цифру к 150–300 ₽.

Модель — `ai-sage/GigaAM-Multilingual` (ru, en, kk, ky, uz). Важно: `GigaAM-v3` для
нас не годится, она русскоязычная. Таджикского нет ни в той, ни в другой.

Потокового режима у модели нет — только сегменты до 25 секунд. Для нажатия кнопки
это нормально: клиент пишет фразу и присылает её целиком. Непрерывное распознавание
на этой модели не строим.

Контракт HTTP-обёртки, которая крутится на ноде рядом с моделью:
    POST {GIGAAM_URL}/v1/recognize?lang=uz
        Content-Type: audio/x-pcm;rate=16000
        тело — сырой LPCM 16 кГц моно 16 бит LE
        → 200 {"text": "..."}  |  4xx/5xx {"detail": "..."}
    GET  {GIGAAM_URL}/health → 200 {"status": "ok", "model": "..."}
"""

import httpx

from app.adapters._timing import measure
from app.config import settings
from app.domain.language import Language
from app.ports.speech import SAMPLE_RATE_HERTZ, Recognition, SpeechUnavailable

PROVIDER = "gigaam"

# Сегмент модели — 25 секунд. Режем с запасом на стороне клиента и здесь.
_CHUNK_BYTES = SAMPLE_RATE_HERTZ * 2 * 25


class GigaAMSpeechRecognition:
    """Речь → текст на своей ноде."""

    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self._base_url = (base_url or settings.gigaam_url).rstrip("/")
        self._timeout = timeout or settings.gigaam_timeout_seconds

    def supports(self, language: Language) -> bool:
        """Языки берём из конфига: состав модели может меняться при дообучении."""
        return language in settings.gigaam_language_set

    async def recognize(self, audio_lpcm: bytes, language: Language) -> Recognition:
        if not self._base_url:
            raise SpeechUnavailable("GIGAAM_URL не задан", provider=PROVIDER)

        with measure() as took:
            parts: list[str] = []
            for start in range(0, max(len(audio_lpcm), 1), _CHUNK_BYTES):
                piece = await self._recognize_chunk(
                    audio_lpcm[start : start + _CHUNK_BYTES], language
                )
                if piece:
                    parts.append(piece)
            text = " ".join(parts)

        return Recognition(text=text, language=language, provider=PROVIDER, duration_ms=took.ms)

    async def _recognize_chunk(self, audio_lpcm: bytes, language: Language) -> str:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/v1/recognize",
                    params={"lang": language},
                    content=audio_lpcm,
                    headers={"Content-Type": f"audio/x-pcm;rate={SAMPLE_RATE_HERTZ}"},
                )
        except httpx.HTTPError as exc:
            # Нода упала или сеть моргнула. Наверх уйдёт деградация, а не 500:
            # ассистент замолчит, связь между сотрудниками продолжит работать.
            raise SpeechUnavailable(f"GPU-нода недоступна: {exc}", provider=PROVIDER) from exc
        if resp.status_code != 200:
            raise SpeechUnavailable(
                f"GigaAM {resp.status_code}: {resp.text[:200]}", provider=PROVIDER
            )
        return resp.json().get("text", "")

    async def healthy(self) -> bool:
        """Живость ноды — для /health приложения и для решения о деградации."""
        if not self._base_url:
            return False
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(f"{self._base_url}/health")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False
