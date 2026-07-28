"""Перевод реплик между сотрудниками.

Реальный движок — Yandex Translate (YandexTranslator). Если ключ не настроен,
default_translator падает на honest-заглушку StubTranslator, которая НЕ выдумывает
перевод, а помечает translated=False (видно, где нужен настоящий MT).
"""

from dataclasses import dataclass
from typing import Protocol

import httpx

from app.config import settings

_TRANSLATE_URL = "https://translate.api.cloud.yandex.net/translate/v2/translate"


@dataclass(frozen=True)
class TranslationResult:
    text: str
    source_language: str
    target_language: str
    translated: bool  # применён ли настоящий движок перевода
    provider: str


class Translator(Protocol):
    """Контракт движка перевода."""

    async def translate(self, text: str, source: str, target: str) -> TranslationResult: ...


class StubTranslator:
    """Заглушка: без реального перевода, с честной пометкой."""

    provider = "stub"

    async def translate(self, text: str, source: str, target: str) -> TranslationResult:
        if source == target:
            return TranslationResult(text, source, target, translated=False, provider="none")
        return TranslationResult(text, source, target, translated=False, provider=self.provider)


class YandexTranslator:
    """Реальный перевод через Yandex Translate API."""

    provider = "yandex"

    async def translate(self, text: str, source: str, target: str) -> TranslationResult:
        if source == target or not text.strip():
            return TranslationResult(text, source, target, translated=False, provider="none")

        payload = {
            "folderId": settings.yandex_folder_id,
            "sourceLanguageCode": source,
            "targetLanguageCode": target,
            "texts": [text],
        }
        headers = {"Authorization": f"Api-Key {settings.yandex_api_key}"}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(_TRANSLATE_URL, json=payload, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"Translate {resp.status_code}: {resp.text}")
        translated_text = resp.json()["translations"][0]["text"]
        return TranslationResult(
            translated_text, source, target, translated=True, provider=self.provider
        )


def _select_translator() -> Translator:
    """Выбрать движок: реальный Yandex при наличии ключа, иначе заглушку."""
    return YandexTranslator() if settings.yandex_enabled else StubTranslator()


# Активный переводчик. Пересобирается на импорте под текущий .env.
default_translator: Translator = _select_translator()
