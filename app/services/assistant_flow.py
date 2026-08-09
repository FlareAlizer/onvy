"""Конвейер голосового запроса: звук с кнопки → ответ в ухо.

Здесь собирается весь путь и меряется каждая стадия. Эти миллисекунды — не
украшение логов: из них складывается бюджет 2.5 секунды и цифры, которые пойдут
в отчёт по пилоту.

Модуль намеренно не знает ни про базу, ни про HTTP: меню и список коллег ему
передают готовыми. Поэтому весь сценарий, включая отказы провайдеров,
проверяется тестами без поднятия инфраструктуры.
"""

import logging
from dataclasses import dataclass, field

from app.domain.intents import (
    Colleague,
    Group,
    Intent,
    IntentKind,
    detect_wake_word,
    parse,
)
from app.domain.language import Language
from app.domain.menu_search import search
from app.ports.answer import AnswerPort, AnswerUnavailable
from app.ports.menu import MenuItemData
from app.ports.speech import (
    SpeechRecognitionPort,
    SpeechSynthesisPort,
    SpeechUnavailable,
)

logger = logging.getLogger(__name__)

# Что говорим, когда своими силами ответить не можем. Молчание в ухе хуже:
# официант стоит перед гостем и не понимает, работает устройство или нет.
ASR_FAILED = "Не расслышал. Повторите, пожалуйста."
ASSISTANT_DOWN = "Ассистент сейчас недоступен. Связь с коллегами работает."
NOTHING_HEARD = "Слушаю. Что подсказать по меню или кому передать?"


@dataclass
class StageMetrics:
    """Сколько заняла каждая стадия конвейера, в миллисекундах."""

    asr_ms: int = 0
    search_ms: int = 0
    answer_ms: int = 0
    tts_ms: int = 0

    @property
    def total_ms(self) -> int:
        return self.asr_ms + self.search_ms + self.answer_ms + self.tts_ms


@dataclass
class AssistantOutcome:
    """Результат обработки нажатия кнопки."""

    kind: IntentKind
    query_text: str = ""
    answer_text: str = ""
    audio: bytes | None = None
    mime_type: str = "audio/mpeg"
    grounded_on: tuple[str, ...] = ()
    # Куда адресована реплика, если это не вопрос ассистенту.
    group: Group | None = None
    person_id: int | None = None
    person_name: str | None = None
    payload: str = ""
    # Ассистента позвали вслух («Онви, …») — выбранный на экране получатель
    # такой вопрос не перехватывает.
    addressed_assistant: bool = False
    # Что именно отвалилось: asr, answer, tts. Пусто — всё отработало штатно.
    degraded: str | None = None
    metrics: StageMetrics = field(default_factory=StageMetrics)


async def handle_voice_query(
    audio_lpcm: bytes,
    *,
    language: Language,
    menu: list[MenuItemData],
    stopped: frozenset[str],
    colleagues: list[Colleague],
    recognition: SpeechRecognitionPort,
    answering: AnswerPort,
    synthesis: SpeechSynthesisPort,
    require_wake_word: bool = False,
) -> AssistantOutcome:
    """Обработать запись с кнопки.

    Отказ любого провайдера не прерывает работу устройства: сотрудник получает
    честную реплику вместо тишины, а рация продолжает работать в любом случае.
    """
    metrics = StageMetrics()

    try:
        recognized = await recognition.recognize(audio_lpcm, language)
    except SpeechUnavailable as exc:
        logger.warning("Распознавание отказало (%s): %s", exc.provider, exc)
        return await _speak_only(
            ASR_FAILED, language, synthesis, metrics, kind=IntentKind.EMPTY, degraded="asr"
        )

    metrics.asr_ms = recognized.duration_ms
    intent = parse(
        recognized.text, colleagues=colleagues, require_wake_word=require_wake_word
    )

    # Режим постоянного прослушивания: обращения не было — это не наш разговор.
    #
    # Микрофон в этом режиме открыт всю смену, поэтому сюда попадает всё, что
    # официант говорит гостям за столами. Такой разговор мы обязаны выбросить
    # целиком и немедленно: гость согласия не давал, и его слова не должны ни
    # сохраниться, ни доехать обратно на телефон, ни попасть на экран
    # управляющего. Поэтому распознанный текст здесь НЕ переносится в результат —
    # дальше этой строки он не живёт.
    #
    # Не «оптимизация» и не забывчивость: если понадобится узнать, что человек
    # сказал не нам, — значит, требование изменилось, и менять его надо осознанно,
    # вместе с юридической частью (спека §7), а не правкой одной строки.
    if intent.kind is IntentKind.IGNORED:
        return AssistantOutcome(kind=intent.kind, metrics=metrics)

    # Реплику в рацию озвучивать ассистентом не надо — её доставит служба связи.
    if intent.kind in (IntentKind.SEND_GROUP, IntentKind.SEND_PERSON):
        if not intent.payload:
            # Адресата назвали, а что передать — нет. Переспрашиваем голосом,
            # иначе коллеге уйдёт пустая реплика.
            addressee = intent.person_name or (intent.group.value if intent.group else "")
            return await _speak_only(
                f"Что передать: {addressee}?" if addressee else NOTHING_HEARD,
                language,
                synthesis,
                metrics,
                kind=IntentKind.EMPTY,
                query_text=recognized.text,
            )
        return _to_comms(intent, recognized.text, metrics)

    if intent.kind is IntentKind.EMPTY:
        return await _speak_only(
            NOTHING_HEARD, language, synthesis, metrics, kind=intent.kind
        )

    return await _answer_from_menu(
        intent=intent,
        addressed_assistant=intent.addressed_assistant,
        query_text=recognized.text,
        language=language,
        menu=menu,
        stopped=stopped,
        answering=answering,
        synthesis=synthesis,
        metrics=metrics,
    )


async def handle_text_query(
    text: str,
    *,
    language: Language,
    menu: list[MenuItemData],
    stopped: frozenset[str],
    answering: AnswerPort,
    synthesis: SpeechSynthesisPort,
    speak: bool = True,
) -> AssistantOutcome:
    """Ответить на вопрос, набранный текстом.

    Тот же путь, что у голоса, минус распознавание: адресата здесь не разбираем —
    человек выбрал ассистента явно, а реплику коллеге отправляет другой роут.
    Обращение «Онви» в начале отрезаем: набирают так же, как говорят.
    """
    metrics = StageMetrics()
    _, body = detect_wake_word(text)
    body = body.strip(" ,.!?") or text.strip()
    if not body:
        return await _speak_only(
            NOTHING_HEARD, language, synthesis, metrics, kind=IntentKind.EMPTY
        )

    return await _answer_from_menu(
        intent=Intent(kind=IntentKind.ASK, payload=body),
        addressed_assistant=True,
        query_text=body,
        language=language,
        menu=menu,
        stopped=stopped,
        answering=answering,
        synthesis=synthesis,
        metrics=metrics,
        speak=speak,
    )


def _to_comms(intent: Intent, query_text: str, metrics: StageMetrics) -> AssistantOutcome:
    return AssistantOutcome(
        kind=intent.kind,
        query_text=query_text,
        payload=intent.payload,
        group=intent.group,
        person_id=intent.person_id,
        person_name=intent.person_name,
        metrics=metrics,
    )


async def _answer_from_menu(
    *,
    intent: Intent,
    addressed_assistant: bool = False,
    query_text: str,
    language: Language,
    menu: list[MenuItemData],
    stopped: frozenset[str],
    answering: AnswerPort,
    synthesis: SpeechSynthesisPort,
    metrics: StageMetrics,
    speak: bool = True,
) -> AssistantOutcome:
    from app.adapters._timing import measure

    with measure() as took:
        facts = search(intent.payload, menu)
    metrics.search_ms = took.ms

    try:
        answer = await answering.answer(
            intent.payload, facts, language, stopped=stopped
        )
    except AnswerUnavailable as exc:
        logger.warning("Ассистент отказал (%s): %s", exc.provider, exc)
        failed = await _speak_only(
            ASSISTANT_DOWN,
            language,
            synthesis,
            metrics,
            kind=IntentKind.ASK,
            query_text=query_text,
            degraded="answer",
        )
        failed.addressed_assistant = addressed_assistant
        return failed

    metrics.answer_ms = answer.duration_ms
    if not speak:
        outcome = AssistantOutcome(
            kind=IntentKind.ASK,
            query_text=query_text,
            answer_text=answer.text,
            metrics=metrics,
        )
    else:
        outcome = await _speak_only(
            answer.text,
            language,
            synthesis,
            metrics,
            kind=IntentKind.ASK,
            query_text=query_text,
        )
    outcome.grounded_on = answer.grounded_on
    outcome.addressed_assistant = addressed_assistant
    return outcome


async def _speak_only(
    text: str,
    language: Language,
    synthesis: SpeechSynthesisPort,
    metrics: StageMetrics,
    *,
    kind: IntentKind,
    query_text: str = "",
    degraded: str | None = None,
) -> AssistantOutcome:
    """Озвучить готовый текст. Отказ синтеза оставляет текст — экран покажет."""
    audio: bytes | None = None
    mime = "audio/mpeg"
    try:
        spoken = await synthesis.synthesize(text, language)
        audio, mime = spoken.audio, spoken.mime_type
        metrics.tts_ms = spoken.duration_ms
    except SpeechUnavailable as exc:
        logger.warning("Синтез отказал (%s): %s", exc.provider, exc)
        degraded = degraded or "tts"

    return AssistantOutcome(
        kind=kind,
        query_text=query_text,
        answer_text=text,
        audio=audio,
        mime_type=mime,
        degraded=degraded,
        metrics=metrics,
    )
