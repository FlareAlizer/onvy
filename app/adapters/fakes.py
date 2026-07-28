"""Поддельные адаптеры для тестов.

Они не изображают успех там, где его нет: умеют отказывать, умеют не знать язык,
умеют возвращать тишину. Тест, который не может воспроизвести отказ, ничего не проверяет.
"""

from dataclasses import dataclass, field

from app.domain.language import Language
from app.ports.answer import Answer
from app.ports.menu import MenuItemData
from app.ports.speech import Recognition, SpeechUnavailable, Synthesis
from app.ports.translation import Translation, TranslationUnavailable


@dataclass
class FakeRecognition:
    """Распознавание с заранее заданным текстом."""

    text: str = "тестовая фраза"
    languages: frozenset[Language] = field(default_factory=lambda: frozenset({"ru"}))
    provider: str = "fake"
    fail_with: str | None = None
    calls: list[tuple[int, Language]] = field(default_factory=list)

    def supports(self, language: Language) -> bool:
        return language in self.languages

    async def recognize(self, audio_lpcm: bytes, language: Language) -> Recognition:
        self.calls.append((len(audio_lpcm), language))
        if self.fail_with:
            raise SpeechUnavailable(self.fail_with, provider=self.provider)
        return Recognition(text=self.text, language=language, provider=self.provider, duration_ms=1)


@dataclass
class FakeSynthesis:
    audio: bytes = b"\x00\x01"
    languages: frozenset[Language] = field(default_factory=lambda: frozenset({"ru"}))
    fail_with: str | None = None

    def supports(self, language: Language) -> bool:
        return language in self.languages

    async def synthesize(self, text: str, language: Language) -> Synthesis:
        if self.fail_with:
            raise SpeechUnavailable(self.fail_with, provider="fake")
        return Synthesis(audio=self.audio, mime_type="audio/mpeg", provider="fake", duration_ms=1)


@dataclass
class FakeTranslation:
    """Перевод, помечающий текст префиксом языка — видно, что он реально применён."""

    fail_with: str | None = None

    def supports(self, source: Language, target: Language) -> bool:
        return True

    async def translate(self, text: str, source: Language, target: Language) -> Translation:
        if self.fail_with:
            raise TranslationUnavailable(self.fail_with, provider="fake")
        if source == target:
            return Translation(text, source, target, False, "none", 0)
        return Translation(f"[{target}] {text}", source, target, True, "fake", 1)


@dataclass
class FakeAnswer:
    text: str = "Ответ ассистента"
    fail_with: str | None = None
    seen_facts: list[list[MenuItemData]] = field(default_factory=list)

    async def answer(
        self,
        question: str,
        facts: list[MenuItemData],
        language: Language,
        *,
        stopped: frozenset[str] = frozenset(),
    ) -> Answer:
        self.seen_facts.append(facts)
        if self.fail_with:
            from app.ports.answer import AnswerUnavailable

            raise AnswerUnavailable(self.fail_with, provider="fake")
        return Answer(
            text=self.text,
            grounded_on=tuple(f.external_id for f in facts),
            provider="fake",
            duration_ms=1,
        )
