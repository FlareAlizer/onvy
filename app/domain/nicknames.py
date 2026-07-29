"""Проверка кличек сотрудников.

Кличка — это то, чем человека окликают голосом, поэтому она обязана быть
однозначной. Плохая кличка ломает продукт тихо и неприятно: два «Азиза» в смене
превращают адресацию в лотерею, кличка «Плов» отправляет вопрос про блюдо живому
человеку, а кличка «Ян» слишком коротка, чтобы распознавание её не потеряло.

Проверка живёт в домене, а не в скрипте подготовки точки: она нужна и при
заведении сотрудника через кабинет управляющего, когда до этого дойдут руки.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.intents import RESERVED_ADDRESS_WORDS
from app.domain.text import normalize, sounds_like, words

# Короче этого распознавание в шуме кличку не удержит: слишком мало звука,
# слишком легко спутать с обрывком соседнего слова.
MIN_NICKNAME_LENGTH = 3


@dataclass(frozen=True)
class NicknameProblem:
    """Что не так с кличкой. Текст сразу человеческий — его читает управляющий."""

    nickname: str
    message: str

    def __str__(self) -> str:
        return f"«{self.nickname}»: {self.message}"


def check_nicknames(
    nicknames: Iterable[str | None],
    *,
    menu_names: Iterable[str] = (),
) -> list[NicknameProblem]:
    """Найти всё, что сделает кличку ненадёжной при голосовом обращении.

    Args:
        nicknames: клички сотрудников точки. Пустые пропускаются — кличка
            необязательна, без неё обращение ищут по первому слову имени.
        menu_names: названия блюд этой точки. Совпадение с блюдом опаснее
            прочего: «плов, подойди» уедет человеку вместо ассистента.
    """
    problems: list[NicknameProblem] = []
    seen: list[str] = []

    menu_words: set[str] = set()
    for name in menu_names:
        menu_words.update(word for word in words(name) if len(word) >= MIN_NICKNAME_LENGTH)

    for raw in nicknames:
        if not raw or not raw.strip():
            continue
        nickname = raw.strip()
        normalized = normalize(nickname)

        if len(normalized) < MIN_NICKNAME_LENGTH:
            problems.append(
                NicknameProblem(
                    nickname,
                    f"слишком короткая, нужно минимум {MIN_NICKNAME_LENGTH} буквы — "
                    "распознавание в шуме потеряет её",
                )
            )
            continue

        if len(words(nickname)) > 1:
            problems.append(
                NicknameProblem(nickname, "должна быть одним словом, окликают одним словом")
            )
            continue

        if any(sounds_like(normalized, reserved) for reserved in RESERVED_ADDRESS_WORDS):
            problems.append(
                NicknameProblem(
                    nickname,
                    "совпадает со служебным словом адресации (отдел или имя ассистента) — "
                    "обращение к отделу перестанет работать",
                )
            )
            continue

        collides_with_menu = next(
            (word for word in menu_words if sounds_like(normalized, word)), None
        )
        if collides_with_menu is not None:
            problems.append(
                NicknameProblem(
                    nickname,
                    f"совпадает со словом из меню («{collides_with_menu}») — "
                    "вопрос про блюдо уйдёт этому сотруднику",
                )
            )
            continue

        twin = next((other for other in seen if sounds_like(normalized, other)), None)
        if twin is not None:
            problems.append(
                NicknameProblem(
                    nickname,
                    f"неотличима на слух от «{twin}» — система не поймёт, кого из двоих звать",
                )
            )
            continue

        seen.append(normalized)

    return problems
