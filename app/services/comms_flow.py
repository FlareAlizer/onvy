"""Доставка реплики между сотрудниками — рация с переводом.

Главный дифференциатор продукта живёт здесь: повар-таджик слышит официанта-узбека
на своём языке. И здесь же главное правило надёжности — реплика доходит всегда.
Если перевод отказал, коллега услышит оригинал с пометкой; если отказал синтез,
получит текст. Тишина недопустима: в зале это читается как «устройство сломалось».

Перевод и озвучка делаются по одному разу на язык, а не на каждого получателя:
в смене из десяти человек языков обычно два-три, и лишние обращения — это и
задержка, и деньги.
"""

import logging
from dataclasses import dataclass, field

from app.domain.language import Language
from app.ports.speech import SpeechSynthesisPort, SpeechUnavailable
from app.ports.translation import TranslationPort, TranslationUnavailable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Recipient:
    employee_id: int
    language: Language


@dataclass
class Delivery:
    """Что именно уходит конкретному сотруднику."""

    employee_id: int
    text: str
    language: Language
    audio: bytes | None
    mime_type: str = "audio/mpeg"
    # False означает, что перевод не применялся: языки совпали или движок отказал.
    translated: bool = False
    # Заполняется, только если перевод был нужен, но не получился.
    translation_failed: bool = False
    translate_ms: int = 0
    tts_ms: int = 0


@dataclass
class Broadcast:
    """Результат отправки одной реплики всем получателям."""

    original_text: str
    source_language: Language
    deliveries: list[Delivery] = field(default_factory=list)

    @property
    def delivered_to(self) -> list[int]:
        return [delivery.employee_id for delivery in self.deliveries]

    @property
    def total_ms(self) -> int:
        """Худшее время доставки — по нему судим, укладываемся ли в бюджет."""
        if not self.deliveries:
            return 0
        return max(d.translate_ms + d.tts_ms for d in self.deliveries)


@dataclass
class _Rendered:
    """Реплика, подготовленная под один язык — переиспользуется для всех, кто на нём."""

    text: str
    translated: bool
    translation_failed: bool
    translate_ms: int
    audio: bytes | None
    mime_type: str
    tts_ms: int


async def deliver(
    text: str,
    *,
    source_language: Language,
    recipients: list[Recipient],
    translation: TranslationPort,
    synthesis: SpeechSynthesisPort,
    speak: bool = True,
) -> Broadcast:
    """Подготовить реплику для каждого получателя на его языке.

    Args:
        text: что сказал отправитель, на его языке.
        source_language: язык отправителя.
        recipients: кому доставляем.
        speak: нужна ли озвучка. Для текстового режима её отключают.
    """
    broadcast = Broadcast(original_text=text, source_language=source_language)
    if not recipients:
        return broadcast

    # Готовим по одному разу на язык — в смене их обычно два-три на десять человек.
    prepared: dict[Language, _Rendered] = {}
    for recipient in recipients:
        if recipient.language not in prepared:
            prepared[recipient.language] = await _render(
                text,
                source_language,
                recipient.language,
                translation=translation,
                synthesis=synthesis,
                speak=speak,
            )
        rendered = prepared[recipient.language]
        broadcast.deliveries.append(
            Delivery(
                employee_id=recipient.employee_id,
                text=rendered.text,
                language=recipient.language,
                audio=rendered.audio,
                mime_type=rendered.mime_type,
                translated=rendered.translated,
                translation_failed=rendered.translation_failed,
                translate_ms=rendered.translate_ms,
                tts_ms=rendered.tts_ms,
            )
        )
    return broadcast


async def _render(
    text: str,
    source: Language,
    target: Language,
    *,
    translation: TranslationPort,
    synthesis: SpeechSynthesisPort,
    speak: bool,
) -> _Rendered:
    """Перевести и озвучить реплику под один язык, переживая отказы."""
    final_text = text
    translated = False
    translation_failed = False
    translate_ms = 0

    if source != target:
        try:
            result = await translation.translate(text, source, target)
            final_text = result.text
            translated = result.translated
            translate_ms = result.duration_ms
        except TranslationUnavailable as exc:
            # Доставляем оригинал: услышать не на своём языке лучше, чем не услышать.
            logger.warning(
                "Перевод %s→%s отказал (%s): %s. Доставляю оригинал.",
                source,
                target,
                exc.provider,
                exc,
            )
            translation_failed = True

    audio: bytes | None = None
    mime = "audio/mpeg"
    tts_ms = 0
    if speak:
        # Если перевод не удался, озвучиваем на языке оригинала — иначе синтез
        # прочитает узбекский текст казахским голосом и выйдет каша.
        voice_language = source if translation_failed else target
        try:
            spoken = await synthesis.synthesize(final_text, voice_language)
            audio, mime, tts_ms = spoken.audio, spoken.mime_type, spoken.duration_ms
        except SpeechUnavailable as exc:
            logger.warning("Синтез для %s отказал (%s): %s", voice_language, exc.provider, exc)

    return _Rendered(
        text=final_text,
        translated=translated,
        translation_failed=translation_failed,
        translate_ms=translate_ms,
        audio=audio,
        mime_type=mime,
        tts_ms=tts_ms,
    )
