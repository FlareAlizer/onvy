"""LLM-ассистент: обвязка YandexGPT (respx) + текстовый эндпоинт /assistant/ask-llm."""

import httpx
import pytest
import respx
from httpx import AsyncClient

from app.config import settings
from app.models.product import Product
from app.services import llm


def _gpt_response(text: str) -> httpx.Response:
    return httpx.Response(
        200, json={"result": {"alternatives": [{"message": {"role": "assistant", "text": text}}]}}
    )


@respx.mock
async def test_answer_over_catalog_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "yandex_api_key", "k", raising=False)
    monkeypatch.setattr(settings, "yandex_folder_id", "f", raising=False)
    route = respx.post("https://llm.api.cloud.yandex.net/foundationModels/v1/completion").mock(
        return_value=_gpt_response("Есть 4 штуки на стеллаже A3.")
    )

    product = Product(name="Наушники Sony", price=34990, stock=4, location="стеллаж A3")
    answer = await llm.answer_over_catalog("где наушники?", [product], "ru")

    assert answer == "Есть 4 штуки на стеллаже A3."
    # В контекст ушли реальные данные каталога.
    sent = route.calls.last.request.content.decode()
    assert "стеллаж A3" in sent


def test_build_context_includes_fields() -> None:
    p = Product(name="Дрель", price=5000, stock=2, location="зона B", description="800 Вт")
    ctx = llm.build_catalog_context([p])
    assert "Дрель" in ctx and "зона B" in ctx and "800 Вт" in ctx


@respx.mock
async def test_ask_llm_endpoint(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "yandex_api_key", "k", raising=False)
    monkeypatch.setattr(settings, "yandex_folder_id", "f", raising=False)
    respx.post("https://llm.api.cloud.yandex.net/foundationModels/v1/completion").mock(
        return_value=_gpt_response("Наушники Sony есть, 4 штуки.")
    )
    await client.post("/api/products", json={"name": "Наушники Sony", "aliases": "наушники"})

    resp = await client.post("/api/assistant/ask-llm", json={"text": "есть наушники?"})
    assert resp.status_code == 200
    assert resp.json()["answer"] == "Наушники Sony есть, 4 штуки."


async def test_ask_llm_requires_yandex(client: AsyncClient) -> None:
    resp = await client.post("/api/assistant/ask-llm", json={"text": "есть наушники?"})
    assert resp.status_code == 503
