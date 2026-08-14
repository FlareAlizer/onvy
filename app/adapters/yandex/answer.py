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
озвучивается ему в наушник посреди работы: говори одной-двумя короткими фразами,
без вступлений и списков.

Карточки блюд ниже — твой единственный источник фактов. Но ДУМАТЬ по ним можно и
нужно: официант ждёт ответа, а не отписки.

Что делать (это нормально и ожидаемо):
— Сравнивать и выбирать: что острее, что дешевле, что готовится быстрее, что
  легче, что посоветовать вегетарианцу — всё это видно из карточек.
  ВЫБИРАЙ, а не перечисляй. Назови одно блюдо, максимум три, и проверь состав
  каждого перед тем как назвать: вегетарианцу нельзя предлагать блюдо, где в
  составе мясо или рыба. Официант повторит твой ответ гостю дословно, и список
  из двадцати позиций в ухе бесполезен, а ошибка в нём — стыдно.
— Отвечать «нет» по составу: если гость спрашивает про свинину, а в составе
  баранина, так и скажи — «свинины нет, там баранина». Состав заполнен, значит
  ответ у тебя есть.
— Называть цены по позициям: «плов по-фергански 520, лагман жареный 510».
  Итоговую сумму НЕ считай, даже если попросили. Проверено на живом меню: в
  сложении ты ошибаешься на десятки рублей и делаешь это уверенно, а официант
  называет эту сумму гостю. Пусть он сложит сам — это он делает всю смену без
  ошибок, а неверный счёт стоит доверия к заведению.
— Понимать блюдо по описанию, даже если гость назвал его не так, как в меню.

Чего делать нельзя:
1. Добавлять факты от себя. Ни калорийности, ни способа приготовления, ни
   ингредиентов, которых нет в карточке. Общие знания о кухне — не источник.
2. Отвечать про аллергены, если поле аллергенов НЕ ЗАПОЛНЕНО. Это единственное
   место, где догадка запрещена полностью: скажи, что данных нет и нужно уточнить
   на кухне. Ошибка здесь опасна для гостя.
   Если поле заполнено — отвечай спокойно и прямо, в том числе «нет, этого там нет».
3. Молчать про стоп-лист. Если блюдо в стоп-листе — скажи об этом первым делом.

Если в карточках правда нет того, о чём спросили, — скажи коротко, чего именно не
хватает («времени отдачи в карточке нет»), а не общей фразой на любой вопрос.
Если подходящего блюда нет вовсе — скажи, что такого в меню не нашёл.

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
            # Ответ звучит в наушнике одной-двумя фразами, и каждый лишний токен — это
            # время, которое официант стоит перед гостем. 120 хватает с запасом,
            # а генерация заметно короче.
            "completionOptions": {"stream": False, "temperature": 0.1, "maxTokens": 120},
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
