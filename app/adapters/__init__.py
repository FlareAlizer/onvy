"""Реализации портов и сборка стека под текущий конфиг.

Это единственное место, где приложение знает имена вендоров. Всё остальное
работает с протоколами из app/ports. Смена провайдера — правка окружения,
а не правка кода: ASR_PROVIDER=gigaam переводит распознавание на свою GPU-ноду.
"""

from functools import lru_cache

from app.adapters.gigaam.speech import GigaAMSpeechRecognition
from app.adapters.routing import LanguageRoutedRecognition
from app.adapters.yandex.answer import YandexGPTAnswer
from app.adapters.yandex.speech import YandexSpeechRecognition, YandexSpeechSynthesis
from app.adapters.yandex.translation import YandexTranslation
from app.config import settings
from app.ports.speech import SpeechRecognitionPort


def _build_provider(name: str) -> SpeechRecognitionPort:
    if name == "gigaam":
        return GigaAMSpeechRecognition()
    return YandexSpeechRecognition()


@lru_cache(maxsize=1)
def recognition() -> SpeechRecognitionPort:
    """Распознавание с маршрутизацией по языку и запасным провайдером."""
    primary = _build_provider(settings.asr_provider)
    fallback = (
        _build_provider(settings.asr_fallback_provider)
        if settings.asr_fallback_provider
        and settings.asr_fallback_provider != settings.asr_provider
        else None
    )
    return LanguageRoutedRecognition(primary, fallback)


@lru_cache(maxsize=1)
def synthesis() -> YandexSpeechSynthesis:
    return YandexSpeechSynthesis()


@lru_cache(maxsize=1)
def translation() -> YandexTranslation:
    return YandexTranslation()


@lru_cache(maxsize=1)
def answering() -> YandexGPTAnswer:
    return YandexGPTAnswer()


def reset() -> None:
    """Сбросить собранный стек. Нужно тестам, которые меняют конфиг."""
    recognition.cache_clear()
    synthesis.cache_clear()
    translation.cache_clear()
    answering.cache_clear()
