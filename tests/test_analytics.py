"""Конвейер аналитики: сегментатор → аналитик (моки LLM) + эндпоинты."""

import json

import pytest
from httpx import AsyncClient

from app.config import settings
from app.services import analytics, llm

_ANALYSIS = {
    "summary": "Продавец презентовал наушники, клиент купил.",
    "kpi_score": 78,
    "deal_analysis": {"is_sold": True, "detected_amount": 34990},
    "sentiment": {"positive": 60, "neutral": 30, "negative": 10},
    "filler_words": [{"word": "ну", "count": 3}],
    "script_compliance": [{"label": "Приветствие", "status": "success"}],
    "strengths": ["Уверенная презентация", "Хорошее закрытие"],
    "weaknesses": ["Перебил клиента", "Не выявил потребности"],
    "mistakes_and_fixes": [{"error": "Перебил клиента", "fix": "Дать договорить и уточнить"}],
    "recommendations": ["Не перебивать", "Задавать открытые вопросы"],
    "transcript_parsed": [
        {"time": "00:00", "speaker": "Сотрудник", "text": "Здравствуйте!", "tags": ["Приветствие"]}
    ],
}


@pytest.fixture
def llm_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    """Включить Yandex и подменить оба LLM-вызова конвейера."""
    monkeypatch.setattr(settings, "yandex_api_key", "test", raising=False)
    monkeypatch.setattr(settings, "yandex_folder_id", "folder", raising=False)

    async def fake_complete_json(system_text: str, user_text: str, **kwargs) -> dict:
        if "модуль сегментации" in system_text:  # LLM №1
            return {"dialogues": ["Диалог один текст", "Диалог два текст"]}
        return _ANALYSIS  # LLM №2

    monkeypatch.setattr(llm, "complete_json", fake_complete_json)


async def test_pipeline_splits_and_analyzes(llm_stub: None) -> None:
    results = await analytics.analyze_recording("сплошная запись смены ...")
    assert len(results) == 2  # сегментатор нашёл 2 диалога
    dialogue, analysis = results[0]
    assert dialogue == "Диалог один текст"
    assert analysis["kpi_score"] == 78


async def test_splitter_falls_back_to_whole_transcript(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Если сегментатор упал — запись разбирается целиком, а не теряется."""

    async def broken(*args, **kwargs):
        raise llm.LLMError("boom")

    monkeypatch.setattr(llm, "complete_json", broken)
    dialogues = await analytics.split_dialogues("текст записи")
    assert dialogues == ["текст записи"]


async def test_analyze_text_endpoint(client: AsyncClient, llm_stub: None) -> None:
    emp = (await client.post("/api/employees", json={"name": "Иван"})).json()

    resp = await client.post(
        "/api/analytics/analyze-text",
        json={"text": "запись смены", "employee_id": emp["id"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["dialogues_found"] == 2
    assert data["analyses"][0]["kpi_score"] == 78
    assert data["analyses"][0]["is_sold"] is True

    # Список и деталка
    listed = (await client.get("/api/analytics/analyses")).json()
    assert len(listed) == 2
    assert listed[0]["summary"].startswith("Продавец")

    detail = (await client.get(f"/api/analytics/analyses/{listed[0]['id']}")).json()
    assert detail["analysis"]["strengths"] == ["Уверенная презентация", "Хорошее закрытие"]


async def test_analytics_requires_yandex(client: AsyncClient) -> None:
    resp = await client.post("/api/analytics/analyze-text", json={"text": "запись"})
    assert resp.status_code == 503


async def test_analyzer_fallback_keeps_json_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Падение аналитика возвращает валидную структуру, а не исключение."""

    async def broken(*args, **kwargs):
        raise llm.LLMError("нет связи")

    monkeypatch.setattr(llm, "complete_json", broken)
    analysis = await analytics.analyze_dialogue("текст диалога")
    assert analysis["kpi_score"] == 0
    json.dumps(analysis)  # сериализуется без ошибок
