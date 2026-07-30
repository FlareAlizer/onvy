"""Выбор адресата на экране и голосом.

Правило, которое здесь проверяется: если человек ткнул пальцем в повара, ему не
надо ещё и называть имя вслух. Но если он назвал вслух — сказанное сильнее
выбранного, переспрашивать нечестно.
"""

from app.api.voice import _redirect_to_chosen, _should_redirect
from app.domain.intents import Colleague, Group, IntentKind, parse
from app.services.assistant_flow import AssistantOutcome, StageMetrics

СМЕНА = [
    Colleague(id=1, name="Азизбек Рахматуллаев", nickname="Азиз"),
    Colleague(id=3, name="Улугбек Каримов", nickname="Шеф"),
]


def фраза(text: str = "два лагмана без острого") -> AssistantOutcome:
    """Распознанная фраза, которую разбор счёл вопросом ассистенту."""
    return AssistantOutcome(
        kind=IntentKind.ASK,
        query_text=text,
        payload=text,
        metrics=StageMetrics(asr_ms=100),
    )


class TestВыборНаЭкране:
    def test_выбранный_человек_становится_адресатом(self):
        итог = _redirect_to_chosen(фраза(), None, 3, СМЕНА)

        assert итог.kind is IntentKind.SEND_PERSON
        assert итог.person_id == 3
        assert итог.person_name == "Шеф"
        assert итог.payload == "два лагмана без острого"

    def test_выбранная_группа_становится_адресатом(self):
        итог = _redirect_to_chosen(фраза(), "кухня", None, СМЕНА)

        assert итог.kind is IntentKind.SEND_GROUP
        assert итог.group is Group.KITCHEN

    def test_метрики_распознавания_сохраняются(self):
        """Замер стадии уже сделан — терять его нельзя, он идёт в отчёт пилота."""
        итог = _redirect_to_chosen(фраза(), "бар", None, СМЕНА)

        assert итог.metrics.asr_ms == 100

    def test_человек_приоритетнее_группы(self):
        """Если пришло и то и другое, личное обращение важнее."""
        итог = _redirect_to_chosen(фраза(), "кухня", 1, СМЕНА)

        assert итог.kind is IntentKind.SEND_PERSON
        assert итог.person_id == 1


class TestГраницы:
    def test_пустая_фраза_не_отправляется(self):
        """Тишина не должна уехать коллеге пустой репликой."""
        итог = _redirect_to_chosen(фраза("   "), "кухня", None, СМЕНА)

        assert итог.kind is IntentKind.ASK

    def test_чужой_сотрудник_не_угадывается(self):
        """Нет в этой точке — отвечаем как обычно, а не шлём наугад."""
        итог = _redirect_to_chosen(фраза(), None, 999, СМЕНА)

        assert итог.kind is IntentKind.ASK

    def test_неизвестная_группа_не_ломает_запрос(self):
        итог = _redirect_to_chosen(фраза(), "подсобка", None, СМЕНА)

        assert итог.kind is IntentKind.ASK

    def test_имя_без_клички_берётся_из_полного(self):
        смена = [Colleague(id=5, name="Марина Петрова", nickname=None)]

        итог = _redirect_to_chosen(фраза(), None, 5, смена)

        assert итог.person_name == "Марина Петрова"


class TestОбращениеКАссистентуВслух:
    """Регрессия: ассистент был недостижим.

    Экран всегда присылал выбранного получателя (по умолчанию «всем»), поэтому
    любой вопрос по меню перехватывался рацией и до ассистента не доходил.
    Названный вслух «Онви» — такое же явное обращение, как «кухня, два лагмана»,
    и должен быть сильнее выбора пальцем.
    """

    def test_онви_разбирается_как_обращение_к_ассистенту(self):
        итог = parse("Онви, что в составе лагмана", colleagues=СМЕНА)

        assert итог.kind is IntentKind.ASK
        assert итог.addressed_assistant is True
        assert итог.payload == "что в составе лагмана"

    def test_вопрос_без_онви_обращением_не_считается(self):
        """Без имени вопрос остаётся вопросом, но выбор на экране его перекроет."""
        итог = parse("что в составе лагмана", colleagues=СМЕНА)

        assert итог.kind is IntentKind.ASK
        assert итог.addressed_assistant is False

    def test_названный_вслух_коллега_сильнее_ассистента(self):
        """«Онви, скажи Шефу…» — это просьба передать, а не вопрос по меню."""
        итог = parse("Онви, скажи Шефу что двадцать первый стол ждёт", colleagues=СМЕНА)

        assert итог.kind is IntentKind.SEND_PERSON
        assert итог.person_name == "Шеф"

    def test_обращение_к_ассистенту_не_перехватывается_экраном(self):
        """Тот самый случай: на экране выбрана кухня, а спросили ассистента."""
        вопрос = фраза("что в составе лагмана")
        вопрос.addressed_assistant = True

        assert _should_redirect(вопрос, "кухня", None) is False
        assert _should_redirect(вопрос, None, 3) is False

    def test_вопрос_без_обращения_уходит_выбранному(self):
        assert _should_redirect(фраза(), "кухня", None) is True
        assert _should_redirect(фраза(), None, 3) is True

    def test_без_выбора_на_экране_вопрос_идёт_ассистенту(self):
        """Экран не навязывает получателя — тогда работает разбор по смыслу."""
        assert _should_redirect(фраза(), None, None) is False

    def test_готовая_реплика_в_рацию_не_переадресуется(self):
        """Отдел уже назван вслух — трогать нечего."""
        реплика = AssistantOutcome(
            kind=IntentKind.SEND_GROUP,
            payload="два лагмана",
            group=Group.KITCHEN,
            metrics=StageMetrics(asr_ms=100),
        )

        assert _should_redirect(реплика, "бар", None) is False
