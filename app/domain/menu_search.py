"""Подбор блюд под вопрос официанта.

Ассистент отвечает только по карточкам, которые сюда попали. Значит качество
ответа определяется этим модулем, а не моделью: не нашли блюдо — ответа не будет,
нашли лишнее — модель начнёт путаться между похожими позициями.

Логика намеренно простая и объяснимая. В шумном зале важнее предсказуемость,
чем хитрость: если официант скажет «лагман», он должен получить лагман, а не
«похожее по эмбеддингу». Эмбеддинги — следующий шаг, когда меню перестанет
помещаться в контекст.
"""

import re

from app.ports.menu import MenuItemData

# Слова, которые есть в любом вопросе и ничего не говорят о блюде.
_STOPWORDS = frozenset(
    {
        "а", "в", "во", "на", "и", "или", "ли", "есть", "у", "нас", "мне", "мы",
        "это", "что", "как", "сколько", "стоит", "цена", "по", "за", "с", "к",
        "нужен", "нужна", "нужно", "хочу", "дай", "покажи", "где", "какой",
        "какая", "какие", "там", "ещё", "еще", "бы", "же", "ну", "вот",
        "составе", "состав", "входит", "блюде", "блюдо", "порция", "грамм",
        "the", "a", "is", "do", "we", "have", "in", "of",
    }
)

# Вес совпадения: попадание в название решает, состав — лишь подсказка.
_WEIGHT_NAME = 4
_WEIGHT_CATEGORY = 2
_WEIGHT_COMPOSITION = 1


def tokenize(text: str) -> set[str]:
    """Значимые слова запроса в нижнем регистре, без ё."""
    words = re.findall(r"\w+", text.lower().replace("ё", "е"))
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def _words(text: str | None) -> set[str]:
    if not text:
        return set()
    return {w for w in re.findall(r"\w+", text.lower().replace("ё", "е")) if len(w) > 2}


# Окончания русских существительных и прилагательных, которые официант меняет
# на лету: «шурпы», «лагмана», «бараниной», «пловом». Сравнение по префиксу здесь
# не работает — «шурпы» и «шурпа» различаются как раз последней буквой.
# Порядок важен: длинные окончания проверяются первыми.
_ENDINGS = (
    "ами", "ями", "ого", "ему", "ому", "ыми", "ими",
    "ой", "ей", "ом", "ем", "ам", "ям", "ах", "ях", "ов", "ев", "ый", "ий", "ая",
    "яя", "ое", "ее", "ые", "ие", "ью",
    "а", "я", "ы", "и", "у", "ю", "е", "о", "й", "ь",
)

# Ниже этой длины стем не режем: «чай», «рис», «лук» должны остаться собой.
_MIN_STEM = 4


def stem(word: str) -> str:
    """Грубая нормализация слова к основе.

    Не морфология, а ровно то, что нужно поиску по меню: убрать падежное
    окончание, если после него остаётся осмысленная основа.
    """
    for ending in _ENDINGS:
        if word.endswith(ending) and len(word) - len(ending) >= _MIN_STEM:
            return word[: -len(ending)]
    return word


def _matches(token: str, target: str) -> bool:
    """Совпадение с поправкой на падежи: «шурпы» ↔ «шурпа», «плову» ↔ «плов»."""
    return token == target or stem(token) == stem(target)


def score(query_tokens: set[str], item: MenuItemData) -> int:
    """Насколько позиция подходит под вопрос."""
    name_words = _words(item.name)
    category_words = _words(item.category)
    composition_words = _words(item.composition)

    total = 0
    for token in query_tokens:
        if any(_matches(token, w) for w in name_words):
            total += _WEIGHT_NAME
        elif any(_matches(token, w) for w in category_words):
            total += _WEIGHT_CATEGORY
        elif any(_matches(token, w) for w in composition_words):
            total += _WEIGHT_COMPOSITION
    return total


def search(question: str, items: list[MenuItemData], limit: int = 5) -> list[MenuItemData]:
    """Подобрать позиции меню под вопрос, по убыванию релевантности.

    Пустой результат — валидный ответ. Он честнее, чем подсунуть модели случайные
    блюда: тогда ассистент скажет «не нашёл такого в меню», и это правда.
    """
    tokens = tokenize(question)
    if not tokens:
        return []

    scored = [(item, score(tokens, item)) for item in items]
    relevant = [(item, value) for item, value in scored if value > 0]
    relevant.sort(key=lambda pair: (-pair[1], pair[0].name))
    return [item for item, _ in relevant[:limit]]
