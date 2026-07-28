"""Порт перевода реплик между сотрудниками.

Правило продукта: отказ перевода никогда не превращается в тишину. Если движок
недоступен, реплика доставляется на языке оригинала с признаком translated=False —
коллега слышит хоть что-то и видит, что перевода не было.
"""

from dataclasses import dataclass
from typing import Protocol

from app.domain.language import Language


class TranslationUnavailable(RuntimeError):
    """Движок перевода недоступен. Сценарий обязан это пережить."""

    def __init__(self, message: str, *, provider: str) -> None:
        super().__init__(message)
        self.provider = provider


@dataclass(frozen=True)
class Translation:
    text: str
    source_language: Language
    target_language: Language
    # False означает «перевод не применялся»: либо языки совпали, либо движок отказал.
    translated: bool
    provider: str
    duration_ms: int


class TranslationPort(Protocol):
    async def translate(self, text: str, source: Language, target: Language) -> Translation: ...

    def supports(self, source: Language, target: Language) -> bool: ...
