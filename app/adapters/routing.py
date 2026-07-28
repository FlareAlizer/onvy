"""Маршрутизация распознавания по языку.

Ни один провайдер не покрывает все языки персонала чайханы: GigaAM-Multilingual
знает ru/en/kk/ky/uz, SpeechKit подтверждён на ru/en/uz/kk, таджикского нет нигде.
Поэтому провайдер выбирается под язык говорящего, а не один на всё приложение.

Так же устроен переход на GPU: меняется ASR_PROVIDER в окружении, домен не знает.
"""

import logging

from app.domain.language import Language
from app.ports.speech import Recognition, SpeechRecognitionPort, SpeechUnavailable

logger = logging.getLogger(__name__)


class LanguageRoutedRecognition:
    """Отдаёт распознавание первому провайдеру, который знает язык.

    Если язык не знает никто, попытка всё равно делается основным провайдером:
    молчащий ассистент хуже, чем ассистент с плохим качеством на редком языке.
    Такой случай логируется — по этим записям видно, где нужен свой fine-tune.
    """

    def __init__(
        self,
        primary: SpeechRecognitionPort,
        fallback: SpeechRecognitionPort | None = None,
    ) -> None:
        self._primary = primary
        self._fallback = fallback

    def supports(self, language: Language) -> bool:
        if self._primary.supports(language):
            return True
        return self._fallback is not None and self._fallback.supports(language)

    async def recognize(self, audio_lpcm: bytes, language: Language) -> Recognition:
        if self._primary.supports(language):
            return await self._recognize_with_retry(self._primary, audio_lpcm, language)

        if self._fallback is not None and self._fallback.supports(language):
            logger.info("Язык %s уходит запасному провайдеру", language)
            return await self._fallback.recognize(audio_lpcm, language)

        logger.warning(
            "Язык %s не поддержан ни одним провайдером — пробуем основным, "
            "качество не гарантировано",
            language,
        )
        return await self._recognize_with_retry(self._primary, audio_lpcm, language)

    async def _recognize_with_retry(
        self, provider: SpeechRecognitionPort, audio_lpcm: bytes, language: Language
    ) -> Recognition:
        """Отказ основного провайдера — не приговор, если есть запасной.

        Ровно этот путь спасает пилот, когда GPU-нода уходит в перезагрузку:
        распознавание молча переезжает в облако.
        """
        try:
            return await provider.recognize(audio_lpcm, language)
        except SpeechUnavailable as exc:
            if self._fallback is None or provider is self._fallback:
                raise
            logger.warning(
                "Провайдер %s отказал (%s) — переключаюсь на запасной", exc.provider, exc
            )
            return await self._fallback.recognize(audio_lpcm, language)
