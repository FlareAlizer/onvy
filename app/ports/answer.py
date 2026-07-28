"""Порт ответа ассистента по меню заведения.

Жёсткое правило, за которое отвечает каждая реализация: ответ строится ТОЛЬКО по
переданным фактам. Ничего не додумывать. Если фактов не хватает — так и сказать.
Цена нарушения — не испорченный UX, а неверный ответ гостю про аллергены,
за который отвечает заведение.
"""

from dataclasses import dataclass
from typing import Protocol

from app.domain.language import Language
from app.ports.menu import MenuItemData


class AnswerUnavailable(RuntimeError):
    """Модель недоступна. Ассистент честно молчит, связь продолжает работать."""

    def __init__(self, message: str, *, provider: str) -> None:
        super().__init__(message)
        self.provider = provider


@dataclass(frozen=True)
class Answer:
    text: str
    # Позиции меню, на которые опирался ответ — для проверки и разбора спорных случаев.
    grounded_on: tuple[str, ...]
    provider: str
    duration_ms: int


class AnswerPort(Protocol):
    async def answer(
        self,
        question: str,
        facts: list[MenuItemData],
        language: Language,
        *,
        stopped: frozenset[str] = frozenset(),
    ) -> Answer:
        """Ответить на вопрос сотрудника по фактам меню.

        Args:
            question: вопрос без обращения «Онви».
            facts: позиции меню, которые подобрал поиск. Пустой список — это
                валидный случай: ответ должен быть «не нашёл, уточните на кухне».
            language: язык, на котором отвечаем — язык профиля сотрудника.
            stopped: внешние id позиций в стоп-листе; о них сообщается первым делом.
        """
        ...
