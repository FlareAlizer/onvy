"""Работа с русским текстом на слух.

Всё, что здесь есть, существует по одной причине: распознавание речи в шумном
зале выдаёт не то, что человек сказал. Падежи, проглоченные окончания, «Азиз»
вместо «Азиза» и наоборот. Сравнивать такие слова напрямую бессмысленно.

Это не морфология и не претендует ею быть — грубые правила, которых хватает,
чтобы узнать блюдо в меню и имя коллеги на смене.
"""

import re

# Окончания, которые официант меняет на лету: «шурпы», «лагмана», «бараниной»,
# «кухне», «Азизу». Длинные проверяются первыми.
_ENDINGS = (
    "ами", "ями", "ого", "ему", "ому", "ыми", "ими",
    "ой", "ей", "ом", "ем", "ам", "ям", "ах", "ях", "ов", "ев", "ый", "ий", "ая",
    "яя", "ое", "ее", "ые", "ие", "ью",
    "а", "я", "ы", "и", "у", "ю", "е", "о", "й", "ь",
)

# Короче этого основу не режем: «чай», «рис», «лук», «бар» должны остаться собой.
MIN_STEM = 3


def normalize(text: str) -> str:
    """Нижний регистр без ё — ниже по цепочке все сравнения идут в этом виде."""
    return text.lower().replace("ё", "е")


def words(text: str | None) -> list[str]:
    """Слова текста по порядку, нормализованные."""
    if not text:
        return []
    return re.findall(r"\w+", normalize(text))


def stem(word: str) -> str:
    """Отрезать падежное окончание, если после него остаётся осмысленная основа."""
    for ending in _ENDINGS:
        if word.endswith(ending) and len(word) - len(ending) >= MIN_STEM:
            return word[: -len(ending)]
    return word


def _distance_within(first: str, second: str, limit: int) -> bool:
    """Отличаются ли слова не больше чем на limit правок.

    Обычное расстояние Левенштейна, но с ранним выходом: нам не нужна точная
    величина, только ответ «достаточно ли похоже».
    """
    if abs(len(first) - len(second)) > limit:
        return False
    previous = list(range(len(second) + 1))
    for i, a in enumerate(first, start=1):
        current = [i]
        for j, b in enumerate(second, start=1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (a != b),
                )
            )
        if min(current) > limit:
            return False
        previous = current
    return previous[-1] <= limit


def sounds_like(spoken: str, target: str) -> bool:
    """Похоже ли услышанное слово на искомое.

    Сначала точное совпадение и совпадение основ — это покрывает падежи.
    Потом одна опечатка распознавания на слово длиной от пяти букв: «Улугбек»
    вполне может приехать как «Улукбек», и терять из-за этого адресата нельзя.
    Короткие слова через опечатки не сравниваем — там любая правка меняет смысл.
    """
    if spoken == target:
        return True

    spoken_stem, target_stem = stem(spoken), stem(target)
    if spoken_stem == target_stem:
        return True

    if min(len(spoken_stem), len(target_stem)) >= 5:
        return _distance_within(spoken_stem, target_stem, 1)
    return False
