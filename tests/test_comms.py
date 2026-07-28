from httpx import AsyncClient

from app.services.translation import StubTranslator


async def _make_employee(client: AsyncClient, name: str, lang: str = "ru") -> int:
    resp = await client.post("/api/employees", json={"name": name, "language": lang})
    return resp.json()["id"]


async def test_send_and_list_message(client: AsyncClient) -> None:
    sender = await _make_employee(client, "Иван")
    recipient = await _make_employee(client, "Пётр")

    resp = await client.post(
        "/api/comms/messages",
        json={"sender_id": sender, "recipient_id": recipient, "text": "Подойди на кассу"},
    )
    assert resp.status_code == 201
    assert resp.json()["source_language"] == "ru"

    listed = await client.get("/api/comms/messages")
    assert listed.status_code == 200
    assert len(listed.json()) == 1


async def test_broadcast_message(client: AsyncClient) -> None:
    sender = await _make_employee(client, "Иван")
    resp = await client.post(
        "/api/comms/messages",
        json={"sender_id": sender, "recipient_id": None, "text": "Всем: акция началась"},
    )
    assert resp.status_code == 201
    assert resp.json()["recipient_id"] is None


async def test_unknown_sender_404(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/comms/messages",
        json={"sender_id": 999, "text": "тест"},
    )
    assert resp.status_code == 404


async def test_translation_stub_same_language() -> None:
    """Одинаковый язык — перевод не нужен, отдаём оригинал."""
    result = await StubTranslator().translate("привет", "ru", "ru")
    assert result.text == "привет"
    assert result.translated is False
    assert result.provider == "none"


async def test_translation_stub_marks_unconnected_engine() -> None:
    """Разные языки: заглушка честно помечает, что реальный MT не подключён."""
    result = await StubTranslator().translate("привет", "ru", "en")
    assert result.translated is False
    assert result.provider == "stub"
