"""Кому адресована фраза: ассистенту или коллеге.

Главный вопрос всего продукта в зале. Ошибка в любую сторону дорогая: вопрос
про блюдо, улетевший на кухню, — это шум в наушнике у поваров; реплика для
кухни, ушедшая ассистенту, — это гость, который не дождался.

Фразы здесь написаны так, как реально говорят на смене, включая то, во что их
превращает распознавание в шуме.
"""

import pytest

from app.domain.intents import Colleague, Group, IntentKind, detect_wake_word, parse

СМЕНА = [
    Colleague(id=1, name="Азизбек Рахматуллаев", nickname="Азиз"),
    Colleague(id=2, name="Малика Юсупова", nickname="Малика"),
    Colleague(id=3, name="Улугбек Каримов", nickname="Шеф"),
]


class TestВопросАссистенту:
    def test_вопрос_про_состав(self):
        intent = parse("Онви, что в составе лагмана", colleagues=СМЕНА)

        assert intent.kind is IntentKind.ASK
        assert intent.payload == "что в составе лагмана"

    def test_кнопка_без_обращения_тоже_вопрос(self):
        """Кнопка нажата осознанно — «Онви» произносить необязательно."""
        intent = parse("сколько стоит плов", colleagues=СМЕНА)

        assert intent.kind is IntentKind.ASK

    def test_упоминание_отдела_в_середине_вопроса_не_обращение(self):
        """«Что там в баре из напитков» — вопрос ассистенту, а не реплика бару."""
        intent = parse("Онви, что там в баре из напитков", colleagues=СМЕНА)

        assert intent.kind is IntentKind.ASK
        assert intent.payload == "что там в баре из напитков"

    def test_упоминание_имени_в_середине_вопроса_не_обращение(self):
        intent = parse("Онви, сколько порций уже отдал Азиз", colleagues=СМЕНА)

        assert intent.kind is IntentKind.ASK


class TestОбращениеКОтделу:
    def test_звательное_обращение_без_глагола(self):
        """Так говорят чаще всего: назвал отдел и сказал что нужно."""
        intent = parse("Онви, кухня, два лагмана без острого", colleagues=СМЕНА)

        assert intent.kind is IntentKind.SEND_GROUP
        assert intent.group is Group.KITCHEN
        assert intent.payload == "два лагмана без острого"

    def test_обращение_через_глагол(self):
        intent = parse("Онви, скажи бару два чая", colleagues=СМЕНА)

        assert intent.kind is IntentKind.SEND_GROUP
        assert intent.group is Group.BAR
        assert intent.payload == "два чая"

    def test_обращение_через_предлог(self):
        intent = parse("Онви, передай на кухню стол пять готов", colleagues=СМЕНА)

        assert intent.kind is IntentKind.SEND_GROUP
        assert intent.group is Group.KITCHEN
        assert intent.payload == "стол пять готов"

    def test_вопрос_коллегам_а_не_ассистенту(self):
        """«Спроси у кухни» — вопрос уходит людям, ассистент тут ни при чём."""
        intent = parse("Онви, спроси у кухни есть ли ещё баранина", colleagues=СМЕНА)

        assert intent.kind is IntentKind.SEND_GROUP
        assert intent.group is Group.KITCHEN
        assert intent.payload == "есть ли ещё баранина"

    def test_падежи_отдела(self):
        for фраза in ("кухне два лагмана", "кухню два лагмана", "кухня два лагмана"):
            intent = parse(фраза, colleagues=СМЕНА)
            assert intent.group is Group.KITCHEN, фраза

    def test_синоним_отдела(self):
        intent = parse("Онви, повара, стол семь ждёт", colleagues=СМЕНА)

        assert intent.group is Group.KITCHEN

    def test_объявление_всем(self):
        intent = parse("Онви, всем, гости на двенадцатый стол", colleagues=СМЕНА)

        assert intent.kind is IntentKind.SEND_GROUP
        assert intent.group is Group.EVERYONE


class TestОбращениеПоКличке:
    def test_кличка_в_начале(self):
        intent = parse("Онви, Азиз, подойди на третий стол", colleagues=СМЕНА)

        assert intent.kind is IntentKind.SEND_PERSON
        assert intent.person_id == 1
        assert intent.person_name == "Азиз"
        assert intent.payload == "подойди на третий стол"

    def test_кличка_в_падеже_после_глагола(self):
        intent = parse("Онви, передай Азизу что стол готов", colleagues=СМЕНА)

        assert intent.kind is IntentKind.SEND_PERSON
        assert intent.person_id == 1

    def test_кличка_не_совпадающая_с_именем(self):
        """К Улугбеку на кухне обращаются «Шеф» — по ней и должно находить."""
        intent = parse("Онви, шеф, что по времени на плов", colleagues=СМЕНА)

        assert intent.kind is IntentKind.SEND_PERSON
        assert intent.person_id == 3

    def test_обращение_по_имени_если_кличку_не_назвали(self):
        intent = parse("Онви, скажи Малике стол освободился", colleagues=СМЕНА)

        assert intent.kind is IntentKind.SEND_PERSON
        assert intent.person_id == 2

    def test_ошибка_распознавания_в_имени_переживается(self):
        """В шуме «Малика» легко приезжает как «Малина» — адресата терять нельзя."""
        intent = parse("Онви, малина, подойди к бару", colleagues=СМЕНА)

        assert intent.kind is IntentKind.SEND_PERSON
        assert intent.person_id == 2

    def test_длинное_имя_не_мешает(self):
        """Полное имя в базе длинное, обращаются по первому слову."""
        intent = parse("Онви, азизбек, забери заказ", colleagues=СМЕНА)

        assert intent.kind is IntentKind.SEND_PERSON
        assert intent.person_id == 1


class TestГраницы:
    def test_адресат_без_сообщения_переспрашивается(self):
        intent = parse("Онви, скажи кухне", colleagues=СМЕНА)

        assert intent.kind is IntentKind.SEND_GROUP
        assert intent.payload == ""

    def test_только_обращение(self):
        intent = parse("Онви", colleagues=СМЕНА)

        assert intent.kind is IntentKind.EMPTY

    def test_пустая_смена_не_ломает_разбор(self):
        intent = parse("Азиз, подойди", colleagues=[])

        assert intent.kind is IntentKind.ASK

    def test_режим_прослушивания_игнорирует_чужой_разговор(self):
        intent = parse(
            "да я вчера в кино ходил", colleagues=СМЕНА, require_wake_word=True
        )

        assert intent.kind is IntentKind.IGNORED


class TestВейкВорд:
    def test_искажения_распознавания(self):
        for вариант in ("Анви", "Энви", "Онвий", "онвы"):
            had, rest = detect_wake_word(f"{вариант} где плов")
            assert had is True, вариант
            assert rest == "где плов"

    def test_склейка_двух_слов(self):
        had, rest = detect_wake_word("он ви скажи кухне")

        assert had is True
        assert rest == "скажи кухне"

    def test_похожее_имя_не_считается_обращением(self):
        """«Анвар» — имя повара, а не вызов ассистента."""
        had, rest = detect_wake_word("Анвар возьми заказ")

        assert had is False
        assert rest == "Анвар возьми заказ"


class TestРазговорСоСтоломНеОбращение:
    """Микрофон в режиме «Онви слушает» открыт всю смену, и в него попадает всё,
    что официант говорит гостям. Такие фразы обязаны остаться чужими.

    Регрессия: правилом было «первые четыре буквы совпали», и под него подходило
    любое длинное слово. Распознавание склеивает соседние слова, поэтому «он
    выбрал» превращалось в «онвыбрал» — а это обращение к ассистенту по старому
    правилу. Обычная фраза официанта про гостя уезжала в облако, обрабатывалась
    ассистентом и оседала в базе, попадая на экран управляющего.
    """

    @pytest.mark.parametrize(
        "фраза",
        [
            "он выбрал плов",
            "он вышел покурить",
            "он выпил чай и ушёл",
            "она вышла в зал",
            "гость сказал что он выберет потом",
            "он высокий такой в кепке",
            "Анвар возьми заказ",
        ],
    )
    def test_обычная_речь_про_гостя_не_будит_ассистента(self, фраза):
        had, rest = detect_wake_word(фраза)

        assert had is False, f"«{фраза}» принято за обращение к ассистенту"
        assert rest == фраза

    @pytest.mark.parametrize(
        "фраза",
        ["Онви что в лагмане", "Анви сколько стоит плов", "Онвию скажи кухне", "он ви подскажи"],
    )
    def test_настоящее_обращение_по_прежнему_слышно(self, фраза):
        """Обратная сторона: ужесточив правило, нельзя оглушить сам продукт."""
        had, _ = detect_wake_word(фраза)

        assert had is True, f"«{фраза}» перестало быть обращением"

    def test_чужой_разговор_в_режиме_прослушивания_игнорируется(self):
        intent = parse(
            "он выбрал плов и салат", colleagues=[], require_wake_word=True
        )

        assert intent.kind is IntentKind.IGNORED
        assert intent.payload == ""


class TestИскажённоеИмяАссистента:
    """«Онви» — выдуманное слово, и распознавание в шуме зала его коверкает.

    Из живых смен приезжали «омви», «онби», «онвя», «унви» — по точному списку
    вариантов всё это отвергалось. Наружу выглядело хуже некуда: кнопка
    отвечает, а голосом ассистент «не слышит», хотя микрофон открыт и фразу он
    получил. Допускаем одну правку от известного написания.
    """

    @pytest.mark.parametrize(
        "искажение",
        ["онви", "анви", "энви", "омви", "онби", "онвы", "онвя", "онве", "унви", "онвю"],
    )
    def test_искажение_распознавания_всё_ещё_обращение(self, искажение):
        had, rest = detect_wake_word(f"{искажение} что в составе лагмана")

        assert had is True, f"«{искажение}» не распознано как обращение"
        assert rest == "что в составе лагмана"

    @pytest.mark.parametrize(
        "слово",
        [
            # Обычная речь смены. Ни одно не должно будить ассистента: иначе
            # разговор с гостем уедет в облако и осядет в базе.
            "они", "оно", "она", "один", "окно", "вино", "обед", "отдай",
            "унеси", "вода", "кофе", "меню", "стол", "гость", "нови", "анод",
            "ответ", "очень", "омлет", "олег", "ольга", "утка", "офис", "орех",
        ],
    )
    def test_обычное_слово_не_будит_ассистента(self, слово):
        had, _ = detect_wake_word(f"{слово} пожалуйста")

        assert had is False, f"«{слово}» принято за обращение к ассистенту"


class TestОбращениеБезОнвиПриОткрытомМикрофоне:
    """Микрофон открыт всю смену, и звать коллегу надо так, как зовут в зале.

    Регрессия: фраза без «Онви» выбрасывалась ДО того, как проверялось, не назван
    ли коллега. То есть «Азиз, подойди к шестому столу» — самое естественное, что
    говорит официант, — не работало вовсе. Рация по голосу была мертва.
    """

    @pytest.mark.parametrize(
        ("фраза", "вид"),
        [
            ("Азиз, подойди к шестому столу", IntentKind.SEND_PERSON),
            ("скажи Азизу что стол готов", IntentKind.SEND_PERSON),
            ("Малика, забери заказ", IntentKind.SEND_PERSON),
            ("кухня, два лагмана без острого", IntentKind.SEND_GROUP),
            ("передай на кухню что стол пять ждёт", IntentKind.SEND_GROUP),
        ],
    )
    def test_коллегу_можно_позвать_без_онви(self, фраза, вид):
        intent = parse(фраза, colleagues=СМЕНА, require_wake_word=True)

        assert intent.kind is вид, f"«{фраза}» не дошло до коллеги"
        assert intent.payload

    @pytest.mark.parametrize(
        "фраза",
        [
            "слушайте я вам сейчас принесу счёт",
            "а вы у нас первый раз",
            "да он вчера с Азизом уходил",
            "мы обычно закрываемся в одиннадцать",
        ],
    )
    def test_разговор_с_гостем_по_прежнему_выбрасывается(self, фраза):
        """Послабление не должно открыть дорогу чужим разговорам: обращением
        считается только слово на позиции обращения, а не любое упоминание."""
        intent = parse(фраза, colleagues=СМЕНА, require_wake_word=True)

        assert intent.kind is IntentKind.IGNORED
        assert intent.payload == ""


class TestТишина:
    """Что делать, когда сказать было нечего, — зависит от того, кто спросил."""

    def test_кнопка_в_тишину_переспрашивает(self):
        """Человек нажал сам и ждёт реакции: молчание в ухе он читает как
        поломку устройства. Регрессия — после правки про обращение без «Онви»
        кнопка в тишину стала молчать."""
        intent = parse("", colleagues=СМЕНА)

        assert intent.kind is IntentKind.EMPTY

    def test_тишина_при_открытом_микрофоне_остаётся_тишиной(self):
        """Шум зала. Отвечать на него вслух нельзя: телефон заговорит поверх
        разговора с гостем."""
        intent = parse("", colleagues=СМЕНА, require_wake_word=True)

        assert intent.kind is IntentKind.IGNORED

    def test_только_онви_переспрашивает_даже_при_открытом_микрофоне(self):
        """Человека позвали по имени — значит обращались к нам."""
        intent = parse("Онви", colleagues=СМЕНА, require_wake_word=True)

        assert intent.kind is IntentKind.EMPTY
