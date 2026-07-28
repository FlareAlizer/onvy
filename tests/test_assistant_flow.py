"""Конвейер голосового запроса целиком, включая отказы провайдеров.

Смысл этих тестов — в деградации. Продукт работает в зале, где что-то отваливается
постоянно: моргнул вайфай, ушла в перезагрузку GPU-нода, кончилась квота облака.
Официант в этот момент стоит перед гостем, и тишина в ухе для него — поломка.
"""

from decimal import Decimal

from app.adapters.fakes import FakeAnswer, FakeRecognition, FakeSynthesis
from app.domain.intents import Group, IntentKind
from app.ports.menu import MenuItemData
from app.services import assistant_flow
from app.services.assistant_flow import handle_voice_query

AUDIO = b"\x00" * 3200
КОЛЛЕГИ = [(1, "Азиз"), (2, "Улугбек")]

МЕНЮ = [
    MenuItemData(
        external_id="lagman",
        name="Лагман",
        category="Горячее",
        price=Decimal("450"),
        composition="лапша, говядина",
        allergens=("глютен",),
    ),
    MenuItemData(
        external_id="plov", name="Плов", category="Горячее", price=Decimal("520")
    ),
]


def стек(
    *,
    распознано: str = "Онви, что в составе лагмана",
    ошибка_asr: str | None = None,
    ошибка_ответа: str | None = None,
    ошибка_tts: str | None = None,
):
    return {
        "recognition": FakeRecognition(
            text=распознано, languages=frozenset({"ru"}), fail_with=ошибка_asr
        ),
        "answering": FakeAnswer(text="Лапша и говядина.", fail_with=ошибка_ответа),
        "synthesis": FakeSynthesis(languages=frozenset({"ru"}), fail_with=ошибка_tts),
    }


async def выполнить(**переопределения):
    стенд = стек(**переопределения)
    return await handle_voice_query(
        AUDIO,
        language="ru",
        menu=МЕНЮ,
        stopped=frozenset(),
        members=КОЛЛЕГИ,
        **стенд,
    )


class TestУспешныйПуть:
    async def test_вопрос_по_меню_возвращает_ответ_и_звук(self):
        итог = await выполнить()

        assert итог.kind is IntentKind.ASK
        assert итог.answer_text == "Лапша и говядина."
        assert итог.audio is not None
        assert итог.degraded is None

    async def test_ответ_помечает_на_каких_блюдах_основан(self):
        """Спорный ответ гостю должно быть чем объяснить."""
        итог = await выполнить()

        assert "lagman" in итог.grounded_on

    async def test_метрики_стадий_заполняются(self):
        итог = await выполнить()

        assert итог.metrics.asr_ms > 0
        assert итог.metrics.answer_ms > 0
        assert итог.metrics.tts_ms > 0
        assert итог.metrics.total_ms >= итог.metrics.asr_ms


class TestМаршрутизацияВРацию:
    async def test_реплика_группе_не_идёт_в_ассистента(self):
        итог = await выполнить(распознано="Онви, скажи кухне два лагмана без острого")

        assert итог.kind is IntentKind.SEND_GROUP
        assert итог.group is Group.KITCHEN
        assert итог.payload == "два лагмана без острого"
        # Ассистент не должен ничего озвучивать — реплику доставит служба связи.
        assert итог.audio is None

    async def test_адресная_реплика_коллеге(self):
        итог = await выполнить(распознано="Онви, передай Азизу стол готов")

        assert итог.kind is IntentKind.SEND_PERSON
        assert итог.person_id == 1

    async def test_только_обращение_получает_приглашение(self):
        итог = await выполнить(распознано="Онви")

        assert итог.kind is IntentKind.EMPTY
        assert итог.answer_text == assistant_flow.NOTHING_HEARD
        assert итог.audio is not None


class TestДеградация:
    async def test_отказ_распознавания_просит_повторить_а_не_молчит(self):
        итог = await выполнить(ошибка_asr="нода недоступна")

        assert итог.degraded == "asr"
        assert итог.answer_text == assistant_flow.ASR_FAILED
        # Голос всё равно есть: официант услышит, что его не расслышали.
        assert итог.audio is not None

    async def test_отказ_модели_честно_сообщает_что_рация_жива(self):
        итог = await выполнить(ошибка_ответа="квота кончилась")

        assert итог.degraded == "answer"
        assert "Связь с коллегами работает" in итог.answer_text

    async def test_отказ_синтеза_оставляет_текст_для_экрана(self):
        итог = await выполнить(ошибка_tts="сеть моргнула")

        assert итог.degraded == "tts"
        assert итог.answer_text == "Лапша и говядина."
        assert итог.audio is None

    async def test_отказ_всего_стека_не_роняет_запрос(self):
        итог = await выполнить(ошибка_asr="нет сети", ошибка_tts="нет сети")

        assert итог.degraded == "asr"
        assert итог.answer_text == assistant_flow.ASR_FAILED
        assert итог.audio is None


class TestПостоянноеПрослушивание:
    async def test_чужой_разговор_игнорируется_молча(self):
        стенд = стек(распознано="да я вчера в кино ходил")
        итог = await handle_voice_query(
            AUDIO,
            language="ru",
            menu=МЕНЮ,
            stopped=frozenset(),
            members=КОЛЛЕГИ,
            require_wake_word=True,
            **стенд,
        )

        assert итог.kind is IntentKind.IGNORED
        assert итог.audio is None
        # Ни модель, ни синтез не дёргались — это ещё и деньги.
        assert итог.metrics.answer_ms == 0
        assert итог.metrics.tts_ms == 0


class TestСтопЛист:
    async def test_стоп_лист_доезжает_до_модели(self):
        """Модель обязана сказать про стоп первой — проверяем, что данные до неё дошли."""
        отвечающий = FakeAnswer(text="Лагман в стопе.")
        итог = await handle_voice_query(
            AUDIO,
            language="ru",
            menu=МЕНЮ,
            stopped=frozenset({"lagman"}),
            members=КОЛЛЕГИ,
            recognition=FakeRecognition(
                text="Онви, есть лагман", languages=frozenset({"ru"})
            ),
            answering=отвечающий,
            synthesis=FakeSynthesis(languages=frozenset({"ru"})),
        )

        assert итог.answer_text == "Лагман в стопе."
        assert отвечающий.seen_facts[0][0].external_id == "lagman"
