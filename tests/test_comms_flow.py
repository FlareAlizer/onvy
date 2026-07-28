"""Доставка реплик с переводом — сценарий, ради которого продукт покупают.

Проверяем и обычный путь (узбек сказал, таджик услышал на своём), и то, что
реплика доходит, когда перевод или синтез отваливаются.
"""

from app.adapters.fakes import FakeSynthesis, FakeTranslation
from app.services.comms_flow import Recipient, deliver

ВСЕ_ЯЗЫКИ = frozenset({"ru", "uz", "kk", "ky", "en", "tg"})


async def отправить(
    text: str = "два лагмана без острого",
    *,
    source: str = "uz",
    recipients: list[Recipient] | None = None,
    ошибка_перевода: str | None = None,
    ошибка_синтеза: str | None = None,
    speak: bool = True,
):
    # Именно `is None`, а не `or`: пустой список получателей — осмысленный случай
    # (никого нет онлайн), и подменять его умолчанием нельзя.
    if recipients is None:
        recipients = [
            Recipient(employee_id=1, language="tg"),
            Recipient(employee_id=2, language="ru"),
        ]
    return await deliver(
        text,
        source_language=source,
        recipients=recipients,
        translation=FakeTranslation(fail_with=ошибка_перевода),
        synthesis=FakeSynthesis(languages=ВСЕ_ЯЗЫКИ, fail_with=ошибка_синтеза),
        speak=speak,
    )


class TestПереводДоходит:
    async def test_каждый_получает_на_своём_языке(self):
        итог = await отправить()

        по_людям = {d.employee_id: d for d in итог.deliveries}
        assert по_людям[1].language == "tg"
        assert по_людям[1].text.startswith("[tg]")
        assert по_людям[2].text.startswith("[ru]")
        assert all(d.translated for d in итог.deliveries)

    async def test_коллега_на_языке_отправителя_получает_оригинал(self):
        итог = await отправить(recipients=[Recipient(employee_id=3, language="uz")])

        доставка = итог.deliveries[0]
        assert доставка.text == "два лагмана без острого"
        assert доставка.translated is False
        assert доставка.translate_ms == 0

    async def test_у_всех_есть_звук(self):
        итог = await отправить()

        assert all(d.audio is not None for d in итог.deliveries)

    async def test_текстовый_режим_не_дёргает_синтез(self):
        итог = await отправить(speak=False)

        assert all(d.audio is None for d in итог.deliveries)
        assert all(d.tts_ms == 0 for d in итог.deliveries)


class TestЭкономияНаЯзыках:
    async def test_один_язык_готовится_один_раз(self):
        """Пять поваров на одном языке — один перевод и один синтез, не пять."""
        синтез = FakeSynthesis(languages=ВСЕ_ЯЗЫКИ)
        перевод = FakeTranslation()
        получатели = [Recipient(employee_id=i, language="tg") for i in range(1, 6)]

        итог = await deliver(
            "стол пять готов",
            source_language="uz",
            recipients=получатели,
            translation=перевод,
            synthesis=синтез,
        )

        assert len(итог.deliveries) == 5
        # Все пятеро получили одну и ту же подготовленную реплику.
        тексты = {d.text for d in итог.deliveries}
        assert len(тексты) == 1


class TestДеградация:
    async def test_отказ_перевода_доставляет_оригинал_с_пометкой(self):
        итог = await отправить(ошибка_перевода="квота кончилась")

        for доставка in итог.deliveries:
            assert доставка.text == "два лагмана без острого"
            assert доставка.translated is False
            assert доставка.translation_failed is True
            # Реплика всё равно звучит — молчание читается как поломка устройства.
            assert доставка.audio is not None

    async def test_отказ_синтеза_оставляет_текст(self):
        итог = await отправить(ошибка_синтеза="сеть моргнула")

        for доставка in итог.deliveries:
            assert доставка.audio is None
            assert доставка.text.startswith("[")

    async def test_никого_онлайн_это_не_ошибка(self):
        итог = await отправить(recipients=[])

        assert итог.deliveries == []
        assert итог.delivered_to == []


class TestМетрики:
    async def test_худшее_время_доставки_считается(self):
        итог = await отправить()

        assert итог.total_ms > 0
        assert итог.total_ms == max(
            d.translate_ms + d.tts_ms for d in итог.deliveries
        )
