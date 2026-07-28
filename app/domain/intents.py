"""Разбор голосовой команды: вопрос ассистенту или реплика в рацию.

Чистая логика без базы и без сети — её легко проверить тестами и легко чинить,
когда живое распознавание начнёт присылать неожиданное.

Что здесь важно понимать про реальность: STT ошибается на имени ассистента и на
падежах. Поэтому и вейк-ворд, и адресат группы ищутся по основам слов, а не по
точному совпадению.
"""

import re
from dataclasses import dataclass
from enum import Enum

# --- Вейк-ворд ---

# Живой STT пишет «Онви» по-разному: Онви, Анви, Энви, Онвий, «он ви».
# Регэксп: [о|а|э] + нв + [и|ы|е] + опциональное «й». Имена вроде «Анвар» не матчит.
_WAKE_RE = re.compile(r"^[оаэ]нв(?:и|ы|е)й?$")
_WAKE_LATIN = frozenset({"onvi", "onvy", "envy", "anvi", "anvy"})


def _is_wake_token(token: str) -> bool:
    return bool(_WAKE_RE.match(token)) or token in _WAKE_LATIN


def detect_wake_word(text: str) -> tuple[bool, str]:
    """Найти обращение «Онви» в начале реплики и отрезать его.

    Ищем среди первых трёх слов: одиночный вариант («Анви») или склейку соседних
    («он ви»). Возвращает (было ли обращение, текст без него).
    """
    tokens = re.findall(r"\w+", text.strip())
    if not tokens:
        return False, ""
    norm = [t.lower().replace("ё", "е") for t in tokens[:3]]

    for i, token in enumerate(norm):
        if _is_wake_token(token):
            return True, " ".join(tokens[i + 1 :]).strip(" ,.!?")

    for i in range(len(norm) - 1):
        if _is_wake_token(norm[i] + norm[i + 1]):
            return True, " ".join(tokens[i + 2 :]).strip(" ,.!?")

    return False, text.strip()


# --- Адресаты ---


class Group(str, Enum):
    """Группы связи в заведении."""

    HALL = "зал"
    KITCHEN = "кухня"
    BAR = "бар"
    EVERYONE = "все"


# Основы слов, по которым узнаём адресата в любом падеже:
# «кухне», «на кухню», «кухня» → KITCHEN.
_GROUP_STEMS: tuple[tuple[str, Group], ...] = (
    ("кухн", Group.KITCHEN),
    ("повар", Group.KITCHEN),
    ("бар", Group.BAR),
    ("зал", Group.HALL),
    ("официант", Group.HALL),
    ("всем", Group.EVERYONE),
    ("все", Group.EVERYONE),
    ("объявл", Group.EVERYONE),
)

# Глаголы обращения: «скажи», «передай», «спроси у», «соедини с».
_SEND_STEMS = ("скаж", "передай", "сообщ", "спрос", "соедин", "свяж", "позов", "вызов")


class IntentKind(str, Enum):
    ASK = "ask"  # вопрос ассистенту по меню
    SEND_GROUP = "send_group"  # реплика группе
    SEND_PERSON = "send_person"  # реплика конкретному сотруднику
    EMPTY = "empty"  # сказали только «Онви» и замолчали
    IGNORED = "ignored"  # режим постоянного прослушивания, обращения не было


@dataclass(frozen=True)
class Intent:
    kind: IntentKind
    # Текст без обращения и без адресата — то, что реально нужно передать или спросить.
    payload: str = ""
    group: Group | None = None
    person_id: int | None = None
    person_name: str | None = None


def _normalize(text: str) -> str:
    return text.lower().replace("ё", "е")


def _find_group(tokens: list[str]) -> tuple[Group, int] | None:
    """Найти группу-адресата и позицию слова, которым она названа."""
    for index, token in enumerate(tokens):
        for stem, group in _GROUP_STEMS:
            if token.startswith(stem):
                return group, index
    return None


def _find_person(
    tokens: list[str], members: list[tuple[int, str]]
) -> tuple[int, str, int] | None:
    """Найти сотрудника по имени. Возвращает (id, имя, позицию в реплике)."""
    for index, token in enumerate(tokens):
        if len(token) <= 2:
            continue
        for member_id, name in members:
            for part in re.findall(r"\w+", _normalize(name)):
                # Сравниваем по началу слова: «Азизу», «Азиза» → «Азиз».
                if len(part) > 2 and (token.startswith(part) or part.startswith(token)):
                    return member_id, name, index
    return None


def parse(
    text: str,
    *,
    members: list[tuple[int, str]] | None = None,
    require_wake_word: bool = False,
) -> Intent:
    """Разобрать распознанную реплику сотрудника.

    Args:
        text: то, что вернуло распознавание.
        members: коллеги, доступные для адресной связи — (id, имя).
        require_wake_word: режим постоянного прослушивания. Без обращения «Онви»
            реплика игнорируется, иначе ассистент лез бы в каждый разговор в зале.
    """
    members = members or []
    had_wake, body = detect_wake_word(text)

    if require_wake_word and not had_wake:
        return Intent(kind=IntentKind.IGNORED)

    body = body.strip(" ,.!?")
    if not body:
        return Intent(kind=IntentKind.EMPTY)

    tokens = re.findall(r"\w+", _normalize(body))
    original_tokens = re.findall(r"\w+", body)
    is_send = any(token.startswith(stem) for token in tokens for stem in _SEND_STEMS)

    person = _find_person(tokens, members)
    if person is not None:
        member_id, name, position = person
        # Имя без глагола обращения — скорее вопрос про блюдо с похожим словом,
        # чем адресная реплика. Требуем явного «скажи/передай/соедини».
        if is_send:
            payload = " ".join(original_tokens[position + 1 :]).strip(" ,.!?")
            return Intent(
                kind=IntentKind.SEND_PERSON,
                payload=payload,
                person_id=member_id,
                person_name=name,
            )

    found = _find_group(tokens)
    if found is not None and is_send:
        group, position = found
        payload = " ".join(original_tokens[position + 1 :]).strip(" ,.!?")
        return Intent(kind=IntentKind.SEND_GROUP, payload=payload, group=group)

    return Intent(kind=IntentKind.ASK, payload=body)
