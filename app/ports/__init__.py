"""Контракты, через которые домен общается с внешним миром.

Ни один модуль в app/domain и app/services не импортирует вендорские библиотеки
напрямую — только эти протоколы. Реализации лежат в app/adapters.
"""

from app.ports.answer import Answer, AnswerPort, AnswerUnavailable
from app.ports.events import EventBusPort
from app.ports.menu import MenuItemData, MenuSourcePort, StopListEntryData
from app.ports.speech import (
    SAMPLE_RATE_HERTZ,
    Recognition,
    SpeechRecognitionPort,
    SpeechSynthesisPort,
    SpeechUnavailable,
    Synthesis,
)
from app.ports.translation import Translation, TranslationPort, TranslationUnavailable

__all__ = [
    "SAMPLE_RATE_HERTZ",
    "Answer",
    "AnswerPort",
    "AnswerUnavailable",
    "EventBusPort",
    "MenuItemData",
    "MenuSourcePort",
    "Recognition",
    "SpeechRecognitionPort",
    "SpeechSynthesisPort",
    "SpeechUnavailable",
    "StopListEntryData",
    "Synthesis",
    "Translation",
    "TranslationPort",
    "TranslationUnavailable",
]
