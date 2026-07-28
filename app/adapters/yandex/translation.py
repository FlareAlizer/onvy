"""Yandex Translate — перевод реплик между сотрудниками.

Остаётся облачным осознанно: покрывает все языки пилота, включая таджикский,
которого нет ни у GigaAM, ни в подтверждённом списке распознавания. Локальный
NLLB на ту же карту сажать не стали — лишний риск ради экономии копеек.
"""

import httpx

from app.adapters._timing import measure
from app.config import settings
from app.domain.language import Language
from app.ports.translation import Translation, TranslationUnavailable

_TRANSLATE_URL = "https://translate.api.cloud.yandex.net/translate/v2/translate"

PROVIDER = "yandex"

# Пары, которые Yandex Translate поддерживает для наших языков.
_SUPPORTED: frozenset[Language] = frozenset({"ru", "en", "uz", "kk", "ky", "tg"})


class YandexTranslation:
    def supports(self, source: Language, target: Language) -> bool:
        return source in _SUPPORTED and target in _SUPPORTED

    async def translate(self, text: str, source: Language, target: Language) -> Translation:
        # Одинаковые языки или пустая реплика — переводить нечего, и это не ошибка.
        if source == target or not text.strip():
            return Translation(
                text=text,
                source_language=source,
                target_language=target,
                translated=False,
                provider="none",
                duration_ms=0,
            )

        payload = {
            "folderId": settings.yandex_folder_id,
            "sourceLanguageCode": source,
            "targetLanguageCode": target,
            "texts": [text],
        }
        headers = {"Authorization": f"Api-Key {settings.yandex_api_key}"}

        with measure() as took:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.post(_TRANSLATE_URL, json=payload, headers=headers)
            except httpx.HTTPError as exc:
                raise TranslationUnavailable(
                    f"Translate недоступен: {exc}", provider=PROVIDER
                ) from exc
            if resp.status_code != 200:
                raise TranslationUnavailable(
                    f"Translate {resp.status_code}: {resp.text[:200]}", provider=PROVIDER
                )
            translated_text = resp.json()["translations"][0]["text"]

        return Translation(
            text=translated_text,
            source_language=source,
            target_language=target,
            translated=True,
            provider=PROVIDER,
            duration_ms=took.ms,
        )
