"""Обёртка над YandexGPT: общий complete() + ассистент над каталогом.

Все LLM-фичи (ассистент, аналитика диалогов, генерация курсов) ходят через одну
функцию complete() — чтобы сменить провайдера (например, на Claude), достаточно
заменить её реализацию.
"""

import json

import httpx

from app.config import settings
from app.models.product import Product

_COMPLETION_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

_LANG_NAME = {
    "ru": "русском",
    "en": "английском",
    "uz": "узбекском",
    "kk": "казахском",
    "tr": "турецком",
}

_SYSTEM_PROMPT = (
    "Ты — Онви, голосовой ассистент опытного продавца. Отвечай коротко (1-3 фразы), "
    "разговорно, чтобы ответ можно было озвучить в наушник.\n"
    "Правила:\n"
    "- Наличие, остаток, цену и где лежит бери СТРОГО из каталога ниже. Эти числа не "
    "выдумывай: если товара в каталоге нет — честно скажи, что наличие и цену нужно "
    "уточнить.\n"
    "- На вопросы о свойствах, составе, применении, пользе, отличиях, совместимости и "
    "«что посоветовать» отвечай как знающий продавец — используй каталог И свои общие "
    "знания о товаре.\n"
    "- Помогай продать: подскажи выгоду, ответь на возражение клиента, предложи "
    "подходящую альтернативу из каталога.\n"
    "Отвечай на {lang} языке."
)


class LLMError(RuntimeError):
    """Ошибка обращения к LLM."""


async def complete(
    system_text: str,
    user_text: str,
    *,
    temperature: float = 0.3,
    max_tokens: int = 500,
) -> str:
    """Один запрос к YandexGPT (модель из настроек). Возвращает текст ответа."""
    payload = {
        "modelUri": f"gpt://{settings.yandex_folder_id}/{settings.yandex_gpt_model}/latest",
        "completionOptions": {"stream": False, "temperature": temperature, "maxTokens": max_tokens},
        "messages": [
            {"role": "system", "text": system_text},
            {"role": "user", "text": user_text},
        ],
    }
    headers = {
        "Authorization": f"Api-Key {settings.yandex_api_key}",
        "x-folder-id": settings.yandex_folder_id,
    }
    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(_COMPLETION_URL, json=payload, headers=headers)
    if resp.status_code != 200:
        raise LLMError(f"YandexGPT {resp.status_code}: {resp.text}")
    return resp.json()["result"]["alternatives"][0]["message"]["text"].strip()


async def complete_json(system_text: str, user_text: str, **kwargs) -> dict:
    """complete() с разбором JSON-ответа (снимает обёртку ```json, если модель добавила)."""
    raw = await complete(system_text, user_text, **kwargs)
    clean = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM вернул не-JSON: {raw[:200]}") from exc


def build_catalog_context(products: list[Product]) -> str:
    """Сериализовать позиции каталога в компактный контекст для LLM."""
    if not products:
        return "(каталог пуст)"
    lines = []
    for p in products:
        parts = [f"«{p.name}»", f"цена {p.price}₽", f"остаток {p.stock} шт"]
        if p.location:
            parts.append(f"где: {p.location}")
        if p.category:
            parts.append(f"категория: {p.category}")
        if p.description:
            parts.append(f"характеристики: {p.description}")
        lines.append("- " + ", ".join(parts))
    return "\n".join(lines)


async def answer_over_catalog(question: str, products: list[Product], language: str = "ru") -> str:
    """Ответить на свободный вопрос по данным каталога через YandexGPT."""
    context = build_catalog_context(products)
    system_text = _SYSTEM_PROMPT.format(lang=_LANG_NAME.get(language, "русском"))
    return await complete(
        f"{system_text}\n\nКАТАЛОГ:\n{context}", question, temperature=0.4, max_tokens=320
    )
