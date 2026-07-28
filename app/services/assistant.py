"""Ядро ассистента-подсказчика: поиск по базе знаний магазина.

ASR/TTS живут на устройстве — сюда приходит текст, отсюда уходит текст.
Логика поиска намеренно простая и прозрачная (keyword-скоринг), чтобы MVP
работал без тяжёлых зависимостей; на рост здесь подключается NLP/эмбеддинги.
"""

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product

# Русские стоп-слова, которые не помогают в матчинге запроса к товару.
_STOPWORDS = {
    "а",
    "в",
    "во",
    "на",
    "и",
    "или",
    "ли",
    "есть",
    "у",
    "нас",
    "мне",
    "мы",
    "это",
    "что",
    "как",
    "сколько",
    "стоит",
    "цена",
    "по",
    "за",
    "с",
    "к",
    "нужен",
    "нужна",
    "нужно",
    "хочу",
    "дай",
    "покажи",
    "где",
    "какой",
    "какая",
    "the",
    "a",
    "is",
    "do",
    "we",
    "have",
}


def _tokenize(text: str) -> set[str]:
    """Разбить текст на значимые токены в нижнем регистре."""
    words = re.findall(r"\w+", text.lower())
    return {w for w in words if len(w) > 1 and w not in _STOPWORDS}


# --- Вейк-ворд и маршрутизация «вопрос ↔ рация» ---

# Живой Yandex STT пишет «Онви» по-разному: Онви, Анви, Энви, Онвий, «он ви».
# Регэксп: [о|а|э] + нв + [и|ы|е] + опц. «й». Не матчит имена вроде «Анвар».
_WAKE_RE = re.compile(r"^[оаэ]нв(?:и|ы|е)й?$")
_WAKE_LATIN = {"onvi", "onvy", "envy", "anvi", "anvy"}


def _is_wake_token(token: str) -> bool:
    return bool(_WAKE_RE.match(token)) or token in _WAKE_LATIN


def detect_wake_word(text: str) -> tuple[bool, str]:
    """Найти обращение «Онви» в начале реплики и отрезать его.

    Ищем среди первых трёх слов: одиночный токен-вариант («Анви») или склейку
    двух соседних («он ви»). Возвращает (было ли обращение, текст без него).
    Если обращения нет — текст как есть.
    """
    tokens = re.findall(r"\w+", text.strip())
    if not tokens:
        return False, ""
    norm = [t.lower().replace("ё", "е") for t in tokens[:3]]
    for i, tok in enumerate(norm):
        if _is_wake_token(tok):
            rest = " ".join(tokens[i + 1 :]).strip(" ,.!?")
            return True, rest
    for i in range(len(norm) - 1):
        if _is_wake_token(norm[i] + norm[i + 1]):
            rest = " ".join(tokens[i + 2 :]).strip(" ,.!?")
            return True, rest
    return False, text.strip()


# Триггеры «соедини меня с …» → уходим в рацию, а не в каталог.
_CONNECT_STEMS = ("соедин", "свяж", "переключ", "позов", "вызов", "рац", "коллег")
# Слова, означающие «всему отделу».
_DEPARTMENT_WORDS = ("отдел", "всем", "весь", "всему", "команд", "все")


def is_connect_request(text: str) -> bool:
    """Похоже ли, что просят соединить с человеком/отделом (а не спрашивают товар)."""
    low = text.lower()
    return any(stem in low for stem in _CONNECT_STEMS)


def _norm(text: str) -> str:
    """Нижний регистр + ё→е, чтобы имена матчились независимо от написания."""
    return text.lower().replace("ё", "е")


def resolve_connect_target(
    text: str, members: list[tuple[int, str]]
) -> tuple[int | None, str | None, bool]:
    """Кому адресовать соединение: (id сотрудника, имя, весь_отдел).

    Сначала ищем конкретного участника отдела по имени в реплике; если не нашли,
    но есть слова «отдел/всем» — это broadcast на весь отдел.
    """
    low = _norm(text)
    for emp_id, name in members:
        for part in re.findall(r"\w+", _norm(name)):
            if len(part) > 2 and part in low:
                return emp_id, name, False
    if any(w in low for w in _DEPARTMENT_WORDS):
        return None, None, True
    return None, None, False


def _product_terms(product: Product) -> set[str]:
    """Все поисковые термины товара: название, категория, синонимы."""
    raw = f"{product.name} {product.category} {product.aliases}"
    return {w for w in re.findall(r"\w+", raw.lower()) if len(w) > 1}


def _score(query_tokens: set[str], product: Product) -> int:
    """Сколько токенов запроса пересеклись с терминами товара."""
    return len(query_tokens & _product_terms(product))


def format_answer(product: Product) -> str:
    """Собрать реплику для озвучивания сотруднику."""
    if product.stock > 0:
        avail = f"в наличии {product.stock} шт"
    else:
        avail = "сейчас нет в наличии"
    parts = [f"{product.name} — {product.price}₽, {avail}."]
    if product.description:
        parts.append(product.description)
    return " ".join(parts)


async def retrieve_context(db: AsyncSession, text: str, max_products: int = 20) -> list[Product]:
    """Подобрать товары для контекста LLM.

    Сначала пробуем найти релевантные по ключевым словам; если ничего не совпало
    (вопрос общий, напр. «что есть из наушников»), отдаём весь каталог до лимита —
    на демо каталог небольшой, это надёжнее пустого контекста.
    """
    matched, found = await answer_query(db, text, limit=max_products)
    if found:
        return matched
    all_products = (await db.execute(select(Product).limit(max_products))).scalars().all()
    return list(all_products)


async def answer_query(db: AsyncSession, text: str, limit: int = 3) -> tuple[list[Product], bool]:
    """Найти релевантные товары по тексту запроса.

    Возвращает (список товаров по убыванию релевантности, найдено ли хоть что-то).
    """
    query_tokens = _tokenize(text)
    if not query_tokens:
        return [], False

    products = (await db.execute(select(Product))).scalars().all()
    scored = [(p, _score(query_tokens, p)) for p in products]
    matched = sorted(
        (p for p, s in scored if s > 0),
        key=lambda p: _score(query_tokens, p),
        reverse=True,
    )[:limit]
    return matched, bool(matched)
