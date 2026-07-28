"""Языки персонала и то, что мы реально умеем на каждом из них.

Честность здесь важнее полноты: если по языку нет распознавания, продукт должен
это знать и деградировать явно, а не делать вид, что всё работает.
"""

from typing import Literal, get_args

Language = Literal["ru", "uz", "kk", "ky", "en", "tg"]

SUPPORTED: tuple[Language, ...] = get_args(Language)

# Языки полного цикла: распознаём, переводим и озвучиваем.
FULL_CYCLE: frozenset[Language] = frozenset({"ru", "uz", "kk", "ky", "en"})

# Языки с частичной поддержкой: перевод и озвучка есть, распознавание под вопросом.
# Таджикского нет у GigaAM-Multilingual, и подтверждения у Yandex STT мы не нашли —
# до ручной проверки на реальном железе считаем распознавание ненадёжным.
DEGRADED: frozenset[Language] = frozenset({"tg"})

DISPLAY_NAMES: dict[Language, str] = {
    "ru": "Русский",
    "uz": "Oʻzbekcha",
    "kk": "Қазақша",
    "ky": "Кыргызча",
    "en": "English",
    "tg": "Тоҷикӣ",
}


def is_supported(language: str) -> bool:
    """Знаем ли мы такой язык вообще."""
    return language in SUPPORTED


def has_reliable_recognition(language: Language) -> bool:
    """Можно ли доверять распознаванию речи на этом языке.

    Используется, чтобы предупредить сотрудника при выборе языка профиля и чтобы
    не приписывать пилоту качество, которого у нас нет.
    """
    return language in FULL_CYCLE


def normalize(language: str | None, fallback: Language = "ru") -> Language:
    """Привести язык к поддерживаемому, не падая на мусоре из внешних систем."""
    if language and is_supported(language):
        return language  # type: ignore[return-value]
    return fallback
