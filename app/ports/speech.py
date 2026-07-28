"""Порты речевого стека: распознавание и синтез.

Домен обращается только к этим контрактам. Кто за ними стоит — Yandex SpeechKit,
GigaAM на своей GPU-ноде или заглушка в тестах — домен не знает и знать не должен.

Каждый порт возвращает длительность своей стадии: бюджет латентности пилота
(≤ 2.5 с p95 от кнопки до звука) складывается из этих чисел, и они же идут в отчёт.
"""

from dataclasses import dataclass
from typing import Protocol

from app.domain.language import Language

# Частота PCM, который присылает браузерный клиент. Единая константа на весь стек:
# и адаптеры, и фронтенд-рекордер обязаны её соблюдать.
SAMPLE_RATE_HERTZ = 16_000


class SpeechUnavailable(RuntimeError):
    """Речевой провайдер недоступен: сеть, квоты, упавшая GPU-нода, битое аудио.

    Ловится на уровне сценария и превращается в честную деградацию, а не в 500.
    """

    def __init__(self, message: str, *, provider: str) -> None:
        super().__init__(message)
        self.provider = provider


@dataclass(frozen=True)
class Recognition:
    """Результат распознавания. Пустой text — это тишина, а не ошибка."""

    text: str
    language: Language
    provider: str
    duration_ms: int


@dataclass(frozen=True)
class Synthesis:
    """Синтезированная речь, готовая к проигрыванию в браузере."""

    audio: bytes
    mime_type: str
    provider: str
    duration_ms: int


class SpeechRecognitionPort(Protocol):
    """Речь → текст.

    Реализация обязана принимать сырой LPCM (16 кГц, моно, 16 бит LE) — это то, что
    отдаёт браузер без перекодирования. Длинное аудио режется реализацией самостоятельно:
    у GigaAM нет потокового режима, сегмент ограничен 25 секундами.
    """

    async def recognize(self, audio_lpcm: bytes, language: Language) -> Recognition: ...

    def supports(self, language: Language) -> bool:
        """Умеет ли этот провайдер данный язык. По нему строится маршрутизация."""
        ...


class SpeechSynthesisPort(Protocol):
    """Текст → речь на языке получателя."""

    async def synthesize(self, text: str, language: Language) -> Synthesis: ...

    def supports(self, language: Language) -> bool: ...
