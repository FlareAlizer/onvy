"""Маршрутизация распознавания по языку и поведение при отказе провайдера.

Это те два случая, которые решают судьбу пилота: официант-киргиз должен быть
услышан, а падение GPU-ноды не должно оставлять зал без ассистента.
"""

import pytest

from app.adapters.fakes import FakeRecognition
from app.adapters.routing import LanguageRoutedRecognition
from app.ports.speech import SpeechUnavailable

AUDIO = b"\x00" * 3200


async def test_язык_основного_провайдера_идёт_к_нему():
    primary = FakeRecognition(text="плов", languages=frozenset({"ru", "uz"}), provider="gigaam")
    fallback = FakeRecognition(text="не должен вызваться", provider="yandex")
    routed = LanguageRoutedRecognition(primary, fallback)

    result = await routed.recognize(AUDIO, "uz")

    assert result.text == "плов"
    assert result.provider == "gigaam"
    assert fallback.calls == []


async def test_язык_которого_нет_у_основного_уходит_запасному():
    # GigaAM не знает таджикского — реальный случай из спеки.
    primary = FakeRecognition(
        languages=frozenset({"ru", "uz", "kk", "ky", "en"}), provider="gigaam"
    )
    fallback = FakeRecognition(text="шурбо", languages=frozenset({"tg"}), provider="yandex")
    routed = LanguageRoutedRecognition(primary, fallback)

    result = await routed.recognize(AUDIO, "tg")

    assert result.text == "шурбо"
    assert result.provider == "yandex"
    assert primary.calls == []


async def test_язык_которого_нет_ни_у_кого_всё_равно_пробуется():
    """Молчащий ассистент хуже плохого качества на редком языке."""
    primary = FakeRecognition(text="хоть что-то", languages=frozenset({"ru"}), provider="gigaam")
    routed = LanguageRoutedRecognition(primary, fallback=None)

    result = await routed.recognize(AUDIO, "tg")

    assert result.text == "хоть что-то"
    assert primary.calls == [(len(AUDIO), "tg")]


async def test_падение_gpu_ноды_переключает_на_облако():
    """Нода в перезагрузке — распознавание молча переезжает в облако."""
    primary = FakeRecognition(
        languages=frozenset({"ru"}), provider="gigaam", fail_with="нода недоступна"
    )
    fallback = FakeRecognition(text="лагман", languages=frozenset({"ru"}), provider="yandex")
    routed = LanguageRoutedRecognition(primary, fallback)

    result = await routed.recognize(AUDIO, "ru")

    assert result.text == "лагман"
    assert result.provider == "yandex"


async def test_без_запасного_отказ_доходит_наверх():
    """Сценарий обязан узнать об отказе, чтобы честно деградировать, а не молчать."""
    primary = FakeRecognition(
        languages=frozenset({"ru"}), provider="gigaam", fail_with="нода недоступна"
    )
    routed = LanguageRoutedRecognition(primary, fallback=None)

    with pytest.raises(SpeechUnavailable) as exc:
        await routed.recognize(AUDIO, "ru")
    assert exc.value.provider == "gigaam"


async def test_отказ_запасного_не_уходит_в_бесконечный_круг():
    primary = FakeRecognition(
        languages=frozenset({"ru"}), provider="gigaam", fail_with="нода недоступна"
    )
    fallback = FakeRecognition(
        languages=frozenset({"ru"}), provider="yandex", fail_with="облако недоступно"
    )
    routed = LanguageRoutedRecognition(primary, fallback)

    with pytest.raises(SpeechUnavailable) as exc:
        await routed.recognize(AUDIO, "ru")
    assert exc.value.provider == "yandex"


def test_поддержка_языка_считается_по_обоим_провайдерам():
    primary = FakeRecognition(languages=frozenset({"ru", "uz"}))
    fallback = FakeRecognition(languages=frozenset({"tg"}))
    routed = LanguageRoutedRecognition(primary, fallback)

    assert routed.supports("uz")
    assert routed.supports("tg")
    assert not routed.supports("en")
