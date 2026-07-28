"""Подбор блюд под вопрос официанта.

Ассистент отвечает только по карточкам, которые сюда попали. Значит качество
ответа определяется этим модулем, а не моделью: не нашли блюдо — ответа не будет,
нашли лишнее — модель начнёт путаться между похожими позициями.

Логика намеренно простая и объяснимая. В шумном зале важнее предсказуемость,
чем хитрость: если официант скажет «лагман», он должен получить лагман, а не
«похожее по эмбеддингу». Эмбеддинги — следующий шаг, когда меню перестанет
помещаться в контекст.
"""

from app.domain.text import sounds_like
from app.domain.text import words as text_words
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
    """Значимые слова запроса — без служебных и слишком коротких."""
    return {w for w in text_words(text) if len(w) > 2 and w not in _STOPWORDS}


def _words(text: str | None) -> set[str]:
    return {w for w in text_words(text) if len(w) > 2}




def score(query_tokens: set[str], item: MenuItemData) -> int:
    """Насколько позиция подходит под вопрос."""
    name_words = _words(item.name)
    category_words = _words(item.category)
    composition_words = _words(item.composition)

    total = 0
    for token in query_tokens:
        if any(sounds_like(token, w) for w in name_words):
            total += _WEIGHT_NAME
        elif any(sounds_like(token, w) for w in category_words):
            total += _WEIGHT_CATEGORY
        elif any(sounds_like(token, w) for w in composition_words):
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
