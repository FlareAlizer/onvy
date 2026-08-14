"""Кому адресована фраза: ассистенту или коллеге.

Это решение принимается по одной распознанной строке, без переспросов — в зале
некогда уточнять. Правила выведены из того, как люди реально говорят на смене:

    «что в составе лагмана»          → вопрос ассистенту
    «кухня, два лагмана без острого» → реплика на кухню, обращение в начале
    «Азиз, подойди на третий»        → реплика Азизу по кличке
    «скажи бару два чая»             → реплика в бар через глагол
    «спроси у кухни есть ли баранина»→ вопрос кухне, а не ассистенту
    «что там в баре из напитков»     → вопрос ассистенту: «бар» упомянут, но
                                       это не обращение

Отсюда два признака обращения: слово-адресат стоит в начале фразы (звательный
падеж, как в живой речи) либо идёт сразу за глаголом обращения. Упоминание
отдела в середине вопроса обращением не считается — иначе половина вопросов про
меню улетала бы коллегам.

Имена сравниваются нестрого: распознавание в шуме коверкает их постоянно,
поэтому у каждого сотрудника есть короткая кличка, а сравнение терпит падеж и
одну ошибку распознавания (см. app/domain/text.py).
"""

from dataclasses import dataclass
from enum import StrEnum

from app.domain.text import normalize, sounds_like, words

# --- Вейк-ворд ---

# Живой STT пишет «Онви» по-разному: Онви, Анви, Энви, Онвий, «он ви».
_WAKE_VARIANTS = ("онви", "анви", "энви", "онвы", "анвы", "энвы", "онвий", "анвий")
_WAKE_LATIN = frozenset({"onvi", "onvy", "envy", "anvi", "anvy"})


_WAKE_PREFIXES = frozenset({"онви", "анви", "энви", "онвы"})

# Насколько длиннее самой основы может быть слово, чтобы всё ещё считаться
# обращением. Двух букв хватает на падежи («Онвию», «Онвика») и не хватает,
# чтобы под правило подошло постороннее слово.
_WAKE_MAX_EXTRA = 2


def _within_one_edit(a: str, b: str) -> bool:
    """Отличаются ли слова не больше чем на одну правку (вставка/замена/пропуск)."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = j = 0
    правка = False
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1
            j += 1
            continue
        if правка:
            return False
        правка = True
        if len(a) == len(b):
            i += 1
        j += 1
    return True


def _is_wake_token(token: str) -> bool:
    """Похоже ли слово на «Онви» настолько, чтобы считать это обращением.

    «Онви» — выдуманное слово, и распознавание в шумном зале его коверкает: из
    живых смен приезжали «омви», «онби», «онвя», «унви». Точный список вариантов
    их не ловил, и наружу это выглядело хуже некуда: кнопка отвечает, а голосом
    ассистент «не слышит» — при том что микрофон открыт и фразу он получил.

    Поэтому допускаем одну правку от известного написания. Цена ошибки
    несимметрична, и обе стороны реальны: пропустить обращение — продукт не
    работает; принять чужое слово — разговор со столом уедет в облако и осядет
    в базе. Поэтому послабление узкое: только слова длиной 4–6 букв и только на
    позиции обращения (начало фразы или сразу после «скажи»/«передай» — это
    обеспечивает detect_wake_word). Список отвергаемых слов закреплён тестами.
    """
    if token in _WAKE_LATIN or token in _WAKE_VARIANTS:
        return True
    if not 4 <= len(token) <= 4 + _WAKE_MAX_EXTRA:
        return False
    # «Онвию», «Онвика» — падежи и уменьшительные от точного написания.
    if token[:4] in _WAKE_PREFIXES:
        return True
    # Одна правка от четырёхбуквенной основы: «омви», «онби», «онвя», «унви».
    # Сравниваем только с основами, не с падежными формами: иначе окно
    # расширится вдвое и в него начнут попадать обычные слова.
    return len(token) == 4 and any(_within_one_edit(token, о) for о in _WAKE_PREFIXES)


def detect_wake_word(text: str) -> tuple[bool, str]:
    """Найти обращение «Онви» в начале реплики и отрезать его."""
    raw = text.strip()
    tokens = words(raw)
    original = _original_words(raw)
    if not tokens:
        return False, ""

    for index, token in enumerate(tokens[:3]):
        if _is_wake_token(token):
            return True, " ".join(original[index + 1 :]).strip(" ,.!?")

    # Распознавание иногда рвёт имя на два слова («он ви»). Склейку принимаем
    # только как точное совпадение с вариантом написания: окончания здесь не
    # прощаем, потому что второе слово в склейке — это чаще всего начало
    # обычного слова, а не хвост имени.
    for index in range(min(len(tokens), 3) - 1):
        склейка = tokens[index] + tokens[index + 1]
        if склейка in _WAKE_VARIANTS or склейка in _WAKE_LATIN:
            return True, " ".join(original[index + 2 :]).strip(" ,.!?")

    return False, raw


def _original_words(text: str) -> list[str]:
    import re

    return re.findall(r"\w+", text)


# --- Адресаты ---


class Group(StrEnum):
    """Отделы заведения — они же группы связи."""

    HALL = "зал"
    KITCHEN = "кухня"
    BAR = "бар"
    EVERYONE = "все"


# Как отдел называют вслух. Сравнение идёт по основам, поэтому падежи покрыты:
# «кухне», «на кухню», «кухня» сводятся к одной основе.
_GROUP_WORDS: tuple[tuple[str, Group], ...] = (
    ("кухня", Group.KITCHEN),
    ("кухне", Group.KITCHEN),
    ("повар", Group.KITCHEN),
    ("повара", Group.KITCHEN),
    ("бар", Group.BAR),
    ("бармен", Group.BAR),
    ("зал", Group.HALL),
    ("официант", Group.HALL),
    ("хостес", Group.HALL),
    ("все", Group.EVERYONE),
    ("всем", Group.EVERYONE),
)

# Слова, которые уже что-то значат для голосовой адресации. Кличка сотрудника
# не должна ни одному из них соответствовать, иначе «бар, подойди» перестанет
# быть обращением к бару. Используется проверкой в app/domain/nicknames.py.
RESERVED_ADDRESS_WORDS: frozenset[str] = frozenset(
    [spoken for spoken, _ in _GROUP_WORDS] + list(_WAKE_VARIANTS) + list(_WAKE_LATIN)
)


# Глаголы обращения. После них следующее слово-адресат — точно обращение.
_ADDRESS_VERBS = (
    "скажи", "скажите", "передай", "передайте", "сообщи", "сообщите",
    "спроси", "спросите", "уточни", "уточните", "позови", "позовите",
    "соедини", "соедините", "свяжи", "свяжите", "вызови", "вызовите",
    "объяви", "объявите",
)

# Предлоги между глаголом и адресатом: «спроси У кухни», «передай НА кухню».
_LINKING = frozenset({"у", "на", "в", "во", "к", "ко", "с", "со"})


@dataclass(frozen=True)
class Colleague:
    """Сотрудник, к которому можно обратиться голосом.

    nickname — короткая кличка на смене. Она важнее полного имени: распознавание
    справляется с «Азиз» заметно лучше, чем с «Азизбек Рахматуллаев», а на кухне
    к человеку и обращаются кличкой.
    """

    id: int
    name: str
    nickname: str | None = None

    def spoken_forms(self) -> tuple[str, ...]:
        forms = [self.nickname] if self.nickname else []
        # Полное имя разбираем по словам: обращаются по первому, а не целиком.
        forms.extend(words(self.name))
        return tuple(form for form in (normalize(f) for f in forms if f) if len(form) > 2)


class IntentKind(StrEnum):
    ASK = "ask"  # вопрос ассистенту по меню
    SEND_GROUP = "send_group"  # реплика отделу
    SEND_PERSON = "send_person"  # реплика конкретному сотруднику
    EMPTY = "empty"  # обращение без продолжения
    IGNORED = "ignored"  # постоянное прослушивание, обращения не было


@dataclass(frozen=True)
class Intent:
    kind: IntentKind
    payload: str = ""
    group: Group | None = None
    person_id: int | None = None
    person_name: str | None = None
    # Ассистента позвали вслух по имени («Онви, что в лагмане»). Такой вопрос
    # адресован именно ему, и выбранный на экране получатель его не перехватывает —
    # ровно так же, как названный вслух отдел сильнее выбора пальцем.
    addressed_assistant: bool = False


@dataclass(frozen=True)
class _Addressee:
    """Найденный адресат и место, где он назван."""

    position: int
    group: Group | None = None
    colleague: Colleague | None = None


def _match_at(token: str, colleagues: list[Colleague]) -> _Addressee | None:
    """Кого называет это слово: отдел, коллегу или никого."""
    for spoken, group in _GROUP_WORDS:
        if sounds_like(token, spoken):
            return _Addressee(position=-1, group=group)

    for colleague in colleagues:
        for form in colleague.spoken_forms():
            if sounds_like(token, form):
                return _Addressee(position=-1, colleague=colleague)
    return None


def _find_addressee(tokens: list[str], colleagues: list[Colleague]) -> _Addressee | None:
    """Найти обращение: в начале фразы или сразу за глаголом обращения.

    Порядок проверок важен. Звательное обращение в начале — самый сильный
    признак, его и смотрим первым.
    """
    if not tokens:
        return None

    # 1. «Кухня, два лагмана» / «Азиз, подойди» — обращение первым словом.
    first = _match_at(tokens[0], colleagues)
    if first is not None:
        return _Addressee(position=0, group=first.group, colleague=first.colleague)

    # 2. «Скажи кухне…», «Спроси у Азиза…» — адресат сразу за глаголом,
    #    возможно через предлог.
    for index, token in enumerate(tokens[:-1]):
        if not any(sounds_like(token, verb) for verb in _ADDRESS_VERBS):
            continue
        candidate_index = index + 1
        if tokens[candidate_index] in _LINKING and candidate_index + 1 < len(tokens):
            candidate_index += 1
        found = _match_at(tokens[candidate_index], colleagues)
        if found is not None:
            return _Addressee(
                position=candidate_index, group=found.group, colleague=found.colleague
            )

    return None


def parse(
    text: str,
    *,
    colleagues: list[Colleague] | None = None,
    require_wake_word: bool = False,
) -> Intent:
    """Разобрать распознанную фразу.

    Args:
        text: то, что вернуло распознавание.
        colleagues: кто на смене — по ним ищется обращение по имени или кличке.
        require_wake_word: режим постоянного прослушивания. Без «Онви» фраза
            игнорируется, иначе ассистент лез бы в каждый разговор в зале.
    """
    colleagues = colleagues or []
    had_wake, body = detect_wake_word(text)

    body = body.strip(" ,.!?")
    if not body:
        return Intent(kind=IntentKind.EMPTY if had_wake else IntentKind.IGNORED)

    tokens = words(body)
    original = _original_words(body)
    addressee = _find_addressee(tokens, colleagues)

    # Микрофон открыт всю смену — значит нужно решить, нам ли эта фраза.
    #
    # Обращением считается не только «Онви», но и названный вслух коллега или
    # отдел: «Азиз, подойди к шестому столу» — это работа, а не разговор с
    # гостем. Так и говорят в зале, и требовать перед этим «Онви» значит сделать
    # рацию неработающей: официант зовёт человека по имени, как звал всегда.
    #
    # Приватность от этого не страдает. Обращением считается только слово на
    # позиции обращения — в начале фразы или сразу за «скажи»/«передай»
    # (см. _find_addressee). Разговор с гостем, где имя коллеги упомянуто в
    # середине, обращением не станет, а фраза вовсе без адресата отбрасывается
    # целиком, как и раньше.
    if require_wake_word and not had_wake and addressee is None:
        return Intent(kind=IntentKind.IGNORED)

    if addressee is None:
        return Intent(kind=IntentKind.ASK, payload=body, addressed_assistant=had_wake)

    payload = " ".join(original[addressee.position + 1 :]).strip(" ,.!?")

    if addressee.colleague is not None:
        return Intent(
            kind=IntentKind.SEND_PERSON,
            payload=payload,
            person_id=addressee.colleague.id,
            person_name=addressee.colleague.nickname or addressee.colleague.name,
        )
    return Intent(kind=IntentKind.SEND_GROUP, payload=payload, group=addressee.group)
