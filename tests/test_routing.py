"""Маршрутизация голосового ассистента: вейк-ворд «Онви» и intent «соединить»."""

import base64

import pytest
from httpx import AsyncClient

from app.services import assistant as asvc
from app.services import llm, speech

# --- Юнит: вейк-ворд ---


def test_wake_word_detected_and_stripped() -> None:
    ok, rest = asvc.detect_wake_word("Онви, где лежат наушники")
    assert ok is True
    assert rest == "где лежат наушники"


def test_wake_word_variants() -> None:
    assert asvc.detect_wake_word("онви соедини с Иваном")[0] is True
    assert asvc.detect_wake_word("Онви!")[0] is True
    assert asvc.detect_wake_word("onvi where is it")[0] is True


def test_wake_word_stt_phonetic_variants() -> None:
    """Живой Yandex STT пишет «Онви» как Анви/Энви/Онвий/«он ви» — все ловим."""
    assert asvc.detect_wake_word("Анви сколько стоит крем для рук")[0] is True
    assert asvc.detect_wake_word("Энви, где лежит товар")[0] is True
    assert asvc.detect_wake_word("Онвий подскажи цену")[0] is True
    assert asvc.detect_wake_word("он ви соедини с Петром") == (True, "соедини с Петром")


def test_wake_word_does_not_match_names() -> None:
    """Имя «Анвар» и обычные слова не должны триггерить ассистента."""
    assert asvc.detect_wake_word("Анвар подойди к кассе")[0] is False
    assert asvc.detect_wake_word("новый товар приехал")[0] is False


def test_no_wake_word_returns_text_untouched() -> None:
    ok, rest = asvc.detect_wake_word("сколько стоит телефон")
    assert ok is False
    assert rest == "сколько стоит телефон"


# --- Юнит: intent соединения ---


def test_is_connect_request() -> None:
    assert asvc.is_connect_request("соедини меня с Петром") is True
    assert asvc.is_connect_request("свяжи с отделом") is True
    assert asvc.is_connect_request("что в составе этого крема") is False


def test_resolve_target_by_name() -> None:
    members = [(2, "Пётр"), (3, "Мария")]
    eid, name, whole = asvc.resolve_connect_target("соедини меня с петром", members)
    assert (eid, name, whole) == (2, "Пётр", False)


def test_resolve_target_whole_department() -> None:
    members = [(2, "Пётр")]
    eid, name, whole = asvc.resolve_connect_target("свяжи со всем отделом", members)
    assert whole is True and eid is None


def test_resolve_target_unknown() -> None:
    members = [(2, "Пётр")]
    eid, name, whole = asvc.resolve_connect_target("соедини с кем-нибудь", members)
    assert (eid, name, whole) == (None, None, False)


# --- Интеграция: эндпоинт /voice/assistant с маршрутизацией ---


@pytest.fixture
def voice_stub(monkeypatch: pytest.MonkeyPatch):
    """Включить Yandex и подменить STT/TTS. Текст распознавания задаётся в тесте."""
    from app.config import settings

    monkeypatch.setattr(settings, "yandex_api_key", "test", raising=False)
    monkeypatch.setattr(settings, "yandex_folder_id", "folder", raising=False)

    state = {"recognized": ""}

    async def fake_recognize(audio: bytes, language: str = "ru") -> str:
        return state["recognized"]

    async def fake_synthesize(text: str, language: str = "ru") -> bytes:
        return b"MP3"

    async def fake_answer(question: str, products, language: str = "ru") -> str:
        return f"Ответ по каталогу на: {question}"

    monkeypatch.setattr(speech, "recognize", fake_recognize)
    monkeypatch.setattr(speech, "synthesize", fake_synthesize)
    monkeypatch.setattr(llm, "answer_over_catalog", fake_answer)
    return state


async def _ask(client: AsyncClient, employee_id: int) -> dict:
    resp = await client.post(
        "/api/voice/assistant",
        data={"employee_id": employee_id},
        files={"audio": ("clip.pcm", b"\x00\x01" * 50, "application/octet-stream")},
    )
    assert resp.status_code == 200
    return resp.json()


async def test_voice_routes_to_connect(client: AsyncClient, voice_stub) -> None:
    await client.post("/api/employees", json={"name": "Иван"})  # id=1, отправитель
    await client.post("/api/employees", json={"name": "Пётр"})  # id=2, цель

    voice_stub["recognized"] = "Онви, соедини меня с Петром"
    data = await _ask(client, 1)

    assert data["intent"] == "connect"
    assert data["wake_word"] is True
    assert data["connect_target_id"] == 2
    assert data["connect_whole_department"] is False


async def test_voice_routes_to_catalog(client: AsyncClient, voice_stub) -> None:
    await client.post("/api/employees", json={"name": "Иван"})
    await client.post("/api/products", json={"name": "Крем Nivea", "aliases": "крем, нивея"})

    voice_stub["recognized"] = "Онви, что в составе крема"
    data = await _ask(client, 1)

    assert data["intent"] == "answer"
    assert "каталог" in data["answer_text"].lower()


async def test_voice_connect_whole_department(client: AsyncClient, voice_stub) -> None:
    await client.post("/api/employees", json={"name": "Иван"})
    await client.post("/api/employees", json={"name": "Пётр"})

    voice_stub["recognized"] = "Онви, свяжи меня со всем отделом"
    data = await _ask(client, 1)

    assert data["intent"] == "connect"
    assert data["connect_whole_department"] is True
    assert data["connect_target_id"] is None


async def test_voice_answer_audio_returned(client: AsyncClient, voice_stub) -> None:
    await client.post("/api/employees", json={"name": "Иван"})
    voice_stub["recognized"] = "Онви, сколько стоит телефон"
    data = await _ask(client, 1)
    assert base64.b64decode(data["audio_base64"]) == b"MP3"


# --- Режим постоянного прослушивания (require_wake) ---


async def _ask_wake(client: AsyncClient, employee_id: int) -> dict:
    resp = await client.post(
        "/api/voice/assistant",
        data={"employee_id": employee_id, "require_wake": "1"},
        files={"audio": ("clip.pcm", b"\x00\x01" * 50, "application/octet-stream")},
    )
    assert resp.status_code == 200
    return resp.json()


async def test_wake_mode_ignores_phrase_without_onvy(client: AsyncClient, voice_stub) -> None:
    """Болтовня без «Онви» игнорируется: ни ответа, ни очков, ни лога."""
    await client.post("/api/employees", json={"name": "Иван"})

    voice_stub["recognized"] = "какая сегодня погода отличная"
    data = await _ask_wake(client, 1)

    assert data["intent"] == "ignored"
    assert data["answer_text"] == ""
    assert data["audio_base64"] == ""

    stats = (await client.get("/api/dashboard/employee/1")).json()
    assert stats["points"] == 0
    assert stats["assistant_queries"] == 0


async def test_wake_mode_processes_phrase_with_onvy(client: AsyncClient, voice_stub) -> None:
    await client.post("/api/employees", json={"name": "Иван"})
    voice_stub["recognized"] = "Онви, сколько стоит крем"
    data = await _ask_wake(client, 1)
    assert data["intent"] == "answer"
    assert data["wake_word"] is True
    assert data["answer_text"] != ""


async def test_wake_mode_ru_fallback_for_foreign_profile(
    client: AsyncClient, voice_stub, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Профиль en, говорит по-русски: en-STT даёт кашу, ru-фолбэк находит «Онви»."""
    await client.post("/api/employees", json={"name": "Vlad", "language": "en"})

    async def fake_recognize_by_lang(audio: bytes, language: str = "ru") -> str:
        if language == "en":
            return "on wee skolka stoit krem"  # каша от английской модели
        return "Онви, сколько стоит крем"

    monkeypatch.setattr(speech, "recognize", fake_recognize_by_lang)

    data = await _ask_wake(client, 1)
    assert data["intent"] == "answer"
    assert data["wake_word"] is True
    assert "Онви" in data["query_text"]
