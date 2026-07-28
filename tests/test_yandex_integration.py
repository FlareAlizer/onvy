"""Проверка реальной обвязки Yandex (парсинг ответов) без сети — через respx-моки.

Доказывает, что HTTP-вызовы STT/TTS/Translate собраны и разбираются верно.
Живая проверка с настоящим ключом — в scripts/smoke_yandex.py.
"""

import httpx
import pytest
import respx

from app.config import settings
from app.services import speech
from app.services.translation import YandexTranslator


@pytest.fixture(autouse=True)
def _enable_yandex(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "yandex_api_key", "test-key", raising=False)
    monkeypatch.setattr(settings, "yandex_folder_id", "test-folder", raising=False)


@respx.mock
async def test_recognize_parses_result() -> None:
    respx.post("https://stt.api.cloud.yandex.net/speech/v1/stt:recognize").mock(
        return_value=httpx.Response(200, json={"result": "сколько стоят наушники"})
    )
    text = await speech.recognize(b"\x00\x01" * 10, "ru")
    assert text == "сколько стоят наушники"


@respx.mock
async def test_recognize_raises_on_error() -> None:
    respx.post("https://stt.api.cloud.yandex.net/speech/v1/stt:recognize").mock(
        return_value=httpx.Response(401, text="unauthorized")
    )
    with pytest.raises(speech.SpeechError):
        await speech.recognize(b"\x00\x01", "ru")


@respx.mock
async def test_synthesize_returns_audio() -> None:
    respx.post("https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize").mock(
        return_value=httpx.Response(200, content=b"MP3DATA")
    )
    audio = await speech.synthesize("привет", "ru")
    assert audio == b"MP3DATA"


@respx.mock
async def test_yandex_translate_real_path() -> None:
    respx.post("https://translate.api.cloud.yandex.net/translate/v2/translate").mock(
        return_value=httpx.Response(200, json={"translations": [{"text": "hello"}]})
    )
    result = await YandexTranslator().translate("привет", "ru", "en")
    assert result.text == "hello"
    assert result.translated is True
    assert result.provider == "yandex"
