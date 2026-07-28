"""Тесты gpu-node/app.py, которые можно прогнать без GPU и без сети.

Модель не грузится по-настоящему: TestClient используется НЕ как context
manager, поэтому lifespan (и, значит, импорт torch/transformers, загрузка
весов) не запускается вовсе. Вместо реальной модели в _state["model"]
подставляется заглушка с методом transcribe(path) -> объект с атрибутом .text
— ровно тот интерфейс, который использует _run_inference().

Что НЕ проверено этими тестами (и не может быть проверено без GPU-ноды):
сама модель, её точность, реальная латентность инференса, прогрев, поведение
Dockerfile/CUDA. Это по-прежнему открытые пункты — см. docs/runbook-gpu-node.md.
"""

import os
import wave
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app as gigaam_app


@pytest.fixture(autouse=True)
def _reset_state():
    """Модель — общий модульный стейт; изолируем тесты друг от друга."""
    gigaam_app._state["model"] = None
    gigaam_app._state["device"] = "unknown"
    yield
    gigaam_app._state["model"] = None
    gigaam_app._state["device"] = "unknown"


@pytest.fixture
def client():
    # Без `with` — lifespan НЕ запускается, torch/transformers не импортируются.
    return TestClient(gigaam_app.app)


def _fake_model(text: str):
    return SimpleNamespace(transcribe=lambda path: SimpleNamespace(text=text))


def _pcm(seconds: float, value: int = 0) -> bytes:
    n = int(gigaam_app.SAMPLE_RATE * seconds)
    sample = int(value).to_bytes(2, "little", signed=True)
    return sample * n


class TestHealth:
    def test_not_ready_before_model_loaded(self, client):
        resp = client.get("/health")
        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "loading"
        assert body["model"] == f"{gigaam_app.MODEL_ID}@{gigaam_app.REVISION}"

    def test_ready_once_model_set(self, client):
        gigaam_app._state["model"] = _fake_model("ok")
        gigaam_app._state["device"] = "cpu"
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {
            "status": "ok",
            "model": f"{gigaam_app.MODEL_ID}@{gigaam_app.REVISION}",
            "device": "cpu",
        }


class TestRecognize:
    def test_unsupported_language_returns_422(self, client):
        gigaam_app._state["model"] = _fake_model("unused")
        resp = client.post("/v1/recognize?lang=tg", content=_pcm(1.0))
        assert resp.status_code == 422
        assert "tg" in resp.json()["detail"]

    def test_missing_language_is_rejected(self, client):
        gigaam_app._state["model"] = _fake_model("unused")
        resp = client.post("/v1/recognize", content=_pcm(1.0))
        assert resp.status_code == 422

    def test_empty_body_returns_empty_text_without_calling_model(self, client):
        calls = []

        def transcribe(path):
            calls.append(path)
            return SimpleNamespace(text="should not happen")

        gigaam_app._state["model"] = SimpleNamespace(transcribe=transcribe)
        resp = client.post("/v1/recognize?lang=ru", content=b"")
        assert resp.status_code == 200
        assert resp.json() == {"text": ""}
        assert calls == []  # тишину не гоняем через модель

    def test_odd_byte_length_returns_422(self, client):
        gigaam_app._state["model"] = _fake_model("unused")
        resp = client.post("/v1/recognize?lang=ru", content=b"\x00\x01\x02")
        assert resp.status_code == 422

    def test_segment_longer_than_25s_returns_413(self, client):
        gigaam_app._state["model"] = _fake_model("unused")
        too_long = _pcm(gigaam_app.MAX_SEGMENT_SECONDS + 1)
        resp = client.post("/v1/recognize?lang=ru", content=too_long)
        assert resp.status_code == 413

    def test_happy_path_returns_recognized_text(self, client):
        gigaam_app._state["model"] = _fake_model("привет мир")
        resp = client.post(
            "/v1/recognize?lang=ru",
            content=_pcm(1.0),
            headers={"Content-Type": "audio/x-pcm;rate=16000"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"text": "привет мир"}

    def test_model_error_returns_500_with_detail(self, client):
        def boom(path):
            raise RuntimeError("модель упала")

        gigaam_app._state["model"] = SimpleNamespace(transcribe=boom)
        resp = client.post("/v1/recognize?lang=ru", content=_pcm(1.0))
        assert resp.status_code == 500
        assert "detail" in resp.json()


class TestPcmToWav:
    def test_round_trips_pcm_into_valid_wav(self):
        pcm = _pcm(0.5, value=1234)
        path = gigaam_app._pcm_to_wav_file(pcm)
        try:
            with wave.open(path, "rb") as w:
                assert w.getnchannels() == 1
                assert w.getsampwidth() == gigaam_app.SAMPLE_WIDTH_BYTES
                assert w.getframerate() == gigaam_app.SAMPLE_RATE
                assert w.readframes(w.getnframes()) == pcm
        finally:
            os.unlink(path)
