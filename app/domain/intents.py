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


def _is_wake_token(token: str) -> bool:
    if token in _WAKE_LATIN or token in _WAKE_VARIANTS:
        return True
    # «Онвию», «Онвика» — окончание переживём, но «Анвар» не должен пройти.
    return len(token) >= 4 and token[:4] in {"онви", "анви", "энви", "онвы"}


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

    for index in range(min(len(tokens), 3) - 1):
        if _is_wake_token(tokens[index] + tokens[index + 1]):
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

    if require_wake_word and not had_wake:
        return Intent(kind=IntentKind.IGNORED)

    body = body.strip(" ,.!?")
    if not body:
        return Intent(kind=IntentKind.EMPTY)

    tokens = words(body)
    original = _original_words(body)
    addressee = _find_addressee(tokens, colleagues)

    if addressee is None:
        return Intent(kind=IntentKind.ASK, payload=body)

    payload = " ".join(original[addressee.position + 1 :]).strip(" ,.!?")

    if addressee.colleague is not None:
        return Intent(
            kind=IntentKind.SEND_PERSON,
            payload=payload,
            person_id=addressee.colleague.id,
            person_name=addressee.colleague.nickname or addressee.colleague.name,
        )
    return Intent(kind=IntentKind.SEND_GROUP, payload=payload, group=addressee.group)
