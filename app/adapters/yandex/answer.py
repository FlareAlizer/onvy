"""Ответ ассистента по меню через YandexGPT.

Здесь живёт самое опасное место продукта. Модель обязана отвечать строго по
карточкам блюд и честно говорить «не знаю», когда поле не заполнено. Официант
транслирует ответ гостю, а информация о составе, аллергенах и весе порции —
зона ответственности заведения по закону о защите прав потребителей.
Поэтому «не знаю» здесь — не недоработка, а требование.
"""

import httpx

from app.adapters._timing import measure
from app.config import settings
from app.domain.language import Language
from app.ports.answer import Answer, AnswerUnavailable
from app.ports.menu import MenuItemData

_COMPLETION_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

PROVIDER = "yandexgpt"

_LANG_NAME: dict[Language, str] = {
    "ru": "русском",
    "en": "английском",
    "uz": "узбекском",
    "kk": "казахском",
    "ky": "киргизском",
    "tg": "таджикском",
}

_SYSTEM_PROMPT = """Ты — Онви, голосовой помощник официанта в чайхане. Твой ответ
озвучивается ему в наушник во время работы: говори одной-двумя короткими фразами,
без вступлений и списков.

Жёсткие правила:
1. Отвечай ТОЛЬКО по карточкам блюд ниже. Ничего не добавляй от себя: ни состав,
   ни калорийность, ни способ приготовления, ни аллергены, которых нет в карточке.
2. Если нужного поля в карточке нет — так и скажи: «в карточке этого нет, уточни
   на кухне». Никогда не угадывай и не отвечай общими знаниями о блюде.
3. Про аллергены отвечай утвердительно только если поле аллергенов заполнено.
   Если оно пустое — обязательно скажи, что данных нет и нужно уточнить на кухне.
   Ошибка здесь опасна для гостя.
4. Если блюдо в стоп-листе — скажи об этом первым делом, до всего остального.
5. Если подходящего блюда в карточках нет — скажи, что не нашёл такого в меню.

Отвечай на {lang} языке."""


def build_menu_context(items: list[MenuItemData], stopped: frozenset[str]) -> str:
    """Собрать карточки блюд для модели.

    Незаполненные поля не выбрасываем молча, а помечаем явно — иначе модель
    примет отсутствие поля за разрешение придумать.
    """
    if not items:
        return "(подходящих блюд не найдено)"

    lines: list[str] = []
    for item in items:
        parts = [f"«{item.name}»"]
        if item.external_id in stopped:
            parts.append("СЕЙЧАС В СТОП-ЛИСТЕ, продавать нельзя")
        if item.price is not None:
            parts.append(f"цена {item.price}₽")
        if item.category:
            parts.append(f"категория: {item.category}")

        parts.append(f"состав: {item.composition}" if item.composition else "состав: НЕ ЗАПОЛНЕН")
        if item.allergens is None:
            parts.append("аллергены: НЕ ЗАПОЛНЕНЫ, отвечать нельзя")
        elif item.allergens:
            parts.append(f"аллергены: {', '.join(item.allergens)}")
        else:
            parts.append("аллергены: проверено, нет")

        if item.weight_grams is not None:
            parts.append(f"выход {item.weight_grams} г")
        if item.spiciness is not None:
            parts.append(f"острота {item.spiciness} из 3")
        if item.prep_time_minutes is not None:
            parts.append(f"готовится {item.prep_time_minutes} мин")

        lines.append("- " + ", ".join(parts))
    return "\n".join(lines)


class YandexGPTAnswer:
    async def answer(
        self,
        question: str,
        facts: list[MenuItemData],
        language: Language,
        *,
        stopped: frozenset[str] = frozenset(),
    ) -> Answer:
        context = build_menu_context(facts, stopped)
        system_text = (
            _SYSTEM_PROMPT.format(lang=_LANG_NAME.get(language, "русском"))
            + f"\n\nКАРТОЧКИ БЛЮД:\n{context}"
        )
        payload = {
            "modelUri": f"gpt://{settings.yandex_folder_id}/{settings.yandex_gpt_model}/latest",
            # Низкая температура: нам нужна дисциплина, а не фантазия.
            "completionOptions": {"stream": False, "temperature": 0.1, "maxTokens": 200},
            "messages": [
                {"role": "system", "text": system_text},
                {"role": "user", "text": question},
            ],
        }
        headers = {
            "Authorization": f"Api-Key {settings.yandex_api_key}",
            "x-folder-id": settings.yandex_folder_id,
        }

        with measure() as took:
            try:
                async with httpx.AsyncClient(timeout=20) as client:
                    resp = await client.post(_COMPLETION_URL, json=payload, headers=headers)
            except httpx.HTTPError as exc:
                raise AnswerUnavailable(f"YandexGPT недоступен: {exc}", provider=PROVIDER) from exc
            if resp.status_code != 200:
                raise AnswerUnavailable(
                    f"YandexGPT {resp.status_code}: {resp.text[:200]}", provider=PROVIDER
                )
            text = resp.json()["result"]["alternatives"][0]["message"]["text"].strip()

        return Answer(
            text=text,
            grounded_on=tuple(item.external_id for item in facts),
            provider=PROVIDER,
            duration_ms=took.ms,
        )
