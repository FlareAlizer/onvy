"""Разбор голосовых команд официанта.

Фразы взяты не из головы, а из того, как реально говорят в зале, и с поправкой
на то, как STT коверкает имя ассистента.
"""

from app.domain.intents import Group, IntentKind, detect_wake_word, parse

КОЛЛЕГИ = [(1, "Азиз"), (2, "Марина Петровна"), (3, "Улугбек")]


class TestВейкВорд:
    def test_чистое_обращение_отрезается(self):
        had, rest = detect_wake_word("Онви, что в составе лагмана")
        assert had is True
        assert rest == "что в составе лагмана"

    def test_искажения_распознавания_ловятся(self):
        # Так SpeechKit пишет «Онви» в шумном зале.
        for вариант in ("Анви", "Энви", "Онвий", "онвы"):
            had, rest = detect_wake_word(f"{вариант} где плов")
            assert had is True, вариант
            assert rest == "где плов"

    def test_склейка_двух_слов(self):
        had, rest = detect_wake_word("он ви скажи кухне")
        assert had is True
        assert rest == "скажи кухне"

    def test_похожее_имя_не_считается_обращением(self):
        """«Анвар» — это имя повара, а не вызов ассистента."""
        had, rest = detect_wake_word("Анвар возьми заказ")
        assert had is False
        assert rest == "Анвар возьми заказ"

    def test_пустая_реплика(self):
        had, rest = detect_wake_word("   ")
        assert had is False
        assert rest == ""


class TestРазборКоманды:
    def test_вопрос_по_меню_идёт_ассистенту(self):
        intent = parse("Онви, что в составе лагмана", members=КОЛЛЕГИ)
        assert intent.kind is IntentKind.ASK
        assert intent.payload == "что в составе лагмана"

    def test_реплика_на_кухню_в_любом_падеже(self):
        for фраза, ожидание in (
            ("Онви, скажи кухне два лагмана без острого", "два лагмана без острого"),
            ("Онви, передай на кухню стол пять готов", "стол пять готов"),
        ):
            intent = parse(фраза, members=КОЛЛЕГИ)
            assert intent.kind is IntentKind.SEND_GROUP, фраза
            assert intent.group is Group.KITCHEN, фраза
            assert intent.payload == ожидание

    def test_реплика_в_бар(self):
        intent = parse("Онви, скажи бару два чая", members=КОЛЛЕГИ)
        assert intent.kind is IntentKind.SEND_GROUP
        assert intent.group is Group.BAR
        assert intent.payload == "два чая"

    def test_объявление_всем(self):
        intent = parse("Онви, скажи всем гости на двенадцатый стол", members=КОЛЛЕГИ)
        assert intent.kind is IntentKind.SEND_GROUP
        assert intent.group is Group.EVERYONE
        assert intent.payload == "гости на двенадцатый стол"

    def test_адресная_реплика_коллеге(self):
        intent = parse("Онви, передай Азизу что стол готов", members=КОЛЛЕГИ)
        assert intent.kind is IntentKind.SEND_PERSON
        assert intent.person_id == 1
        assert intent.person_name == "Азиз"
        assert intent.payload == "что стол готов"

    def test_имя_коллеги_в_вопросе_не_делает_реплику(self):
        """Без глагола обращения это вопрос ассистенту, а не отправка сообщения."""
        intent = parse("Онви, сколько стоит плов", members=[(9, "Плов Мастер")])
        assert intent.kind is IntentKind.ASK

    def test_только_обращение_без_продолжения(self):
        intent = parse("Онви", members=КОЛЛЕГИ)
        assert intent.kind is IntentKind.EMPTY

    def test_без_вейк_ворда_кнопка_всё_равно_работает(self):
        """Кнопка нажата осознанно — обрабатываем, даже если ассистента не позвали."""
        intent = parse("что в составе шурпы", members=КОЛЛЕГИ)
        assert intent.kind is IntentKind.ASK
        assert intent.payload == "что в составе шурпы"

    def test_режим_прослушивания_игнорирует_чужие_разговоры(self):
        intent = parse(
            "да я вчера в кино ходил", members=КОЛЛЕГИ, require_wake_word=True
        )
        assert intent.kind is IntentKind.IGNORED

    def test_режим_прослушивания_реагирует_на_обращение(self):
        intent = parse(
            "Онви, есть ли самса", members=КОЛЛЕГИ, require_wake_word=True
        )
        assert intent.kind is IntentKind.ASK
        assert intent.payload == "есть ли самса"
