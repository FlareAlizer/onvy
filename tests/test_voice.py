import base64

import pytest
from httpx import AsyncClient

from app.config import settings
from app.services import llm, speech


@pytest.fixture
def yandex_stub(monkeypatch: pytest.MonkeyPatch) -> str:
    """Включить речевой стек и подменить сетевые вызовы (STT/TTS/LLM) на фейки."""
    monkeypatch.setattr(settings, "yandex_api_key", "test", raising=False)
    monkeypatch.setattr(settings, "yandex_folder_id", "folder", raising=False)

    async def fake_recognize(audio: bytes, language: str = "ru") -> str:
        return "где лежат наушники sony"

    async def fake_synthesize(text: str, language: str = "ru") -> bytes:
        return b"FAKE_MP3_BYTES"

    async def fake_answer(question: str, products, language: str = "ru") -> str:
        return "Наушники Sony на стеллаже A3, есть 4 штуки."

    monkeypatch.setattr(speech, "recognize", fake_recognize)
    monkeypatch.setattr(speech, "synthesize", fake_synthesize)
    monkeypatch.setattr(llm, "answer_over_catalog", fake_answer)
    return "ok"


async def test_voice_assistant_llm_happy_path(client: AsyncClient, yandex_stub: str) -> None:
    await client.post("/api/employees", json={"name": "Иван"})
    await client.post(
        "/api/products",
        json={
            "name": "Наушники Sony WH-1000XM5",
            "price": 34990,
            "stock": 4,
            "location": "стеллаж A3",
            "aliases": "сони, наушники",
        },
    )

    resp = await client.post(
        "/api/voice/assistant",
        data={"employee_id": 1},
        files={"audio": ("clip.pcm", b"\x00\x01" * 100, "application/octet-stream")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["query_text"] == "где лежат наушники sony"
    assert data["answer_text"] == "Наушники Sony на стеллаже A3, есть 4 штуки."
    assert base64.b64decode(data["audio_base64"]) == b"FAKE_MP3_BYTES"


async def test_voice_assistant_awards_points_and_logs(
    client: AsyncClient, yandex_stub: str
) -> None:
    await client.post("/api/employees", json={"name": "Иван"})
    await client.post("/api/products", json={"name": "Наушники Sony", "aliases": "сони, наушники"})

    await client.post(
        "/api/voice/assistant",
        data={"employee_id": 1},
        files={"audio": ("clip.pcm", b"\x00\x01" * 100, "application/octet-stream")},
    )

    stats = (await client.get("/api/dashboard/employee/1")).json()
    assert stats["assistant_queries"] == 1
    assert stats["points"] == 2  # POINTS_ASSISTANT_FOUND (контекст найден)


async def test_voice_requires_yandex(client: AsyncClient) -> None:
    """Без ключа голосовой роут честно отвечает 503, а не падает."""
    await client.post("/api/employees", json={"name": "Иван"})
    resp = await client.post(
        "/api/voice/assistant",
        data={"employee_id": 1},
        files={"audio": ("clip.pcm", b"\x00\x01", "application/octet-stream")},
    )
    assert resp.status_code == 503
