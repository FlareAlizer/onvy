"""Выбор адресата на экране и голосом.

Правило, которое здесь проверяется: если человек ткнул пальцем в повара, ему не
надо ещё и называть имя вслух. Но если он назвал вслух — сказанное сильнее
выбранного, переспрашивать нечестно.
"""

from app.api.voice import _redirect_to_chosen
from app.domain.intents import Colleague, Group, IntentKind
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
