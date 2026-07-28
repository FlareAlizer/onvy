"""Голосовой ассистент: аудио запроса → распознавание → подсказка → озвучка.

Аудио приходит из браузера как сырой LPCM (16 kHz, mono, 16-bit LE) — см.
web/js/recorder.js. Ответ возвращаем текстом + MP3 (base64) для проигрывания.
"""

import base64
import logging

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.deps import require_api_key
from app.models.assistant_log import AssistantLog
from app.models.employee import Employee
from app.schemas.voice import VoiceAssistantResult
from app.services import assistant as assistant_service
from app.services import gamification, llm, speech
from app.services.llm import LLMError
from app.services.speech import SpeechError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voice"], dependencies=[Depends(require_api_key)])


def _require_yandex() -> None:
    if not settings.yandex_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Речевой стек Yandex не настроен: заполни YANDEX_API_KEY и YANDEX_FOLDER_ID",
        )


async def _department_members(db: AsyncSession, employee: Employee | None) -> list[tuple[int, str]]:
    """Коллеги по отделу (кроме самого сотрудника) — для маршрутизации в рацию."""
    if employee is None or employee.department_id is None:
        return []
    rows = (
        await db.execute(
            select(Employee.id, Employee.name).where(
                Employee.department_id == employee.department_id,
                Employee.id != employee.id,
            )
        )
    ).all()
    return [(r[0], r[1]) for r in rows]


@router.post("/voice/assistant", response_model=VoiceAssistantResult)
async def voice_assistant(
    audio: UploadFile,
    employee_id: int | None = Form(default=None),
    require_wake: bool = Form(default=False),
    db: AsyncSession = Depends(get_session),
) -> VoiceAssistantResult:
    """Голосовой запрос сотрудника: активация «Онви» → маршрут в каталог или рацию.

    - «Онви, где лежит X / что в составе Y» → подсказка по каталогу голосом.
    - «Онви, соедини меня с Иваном / со всем отделом» → intent=connect, клиент
      подставляет получателя в рацию.
    - require_wake=true — режим постоянного прослушивания: фразы БЕЗ «Онви»
      игнорируются (intent=ignored), чтобы ассистент не реагировал на всё подряд.
    """
    _require_yandex()

    employee = await db.get(Employee, employee_id) if employee_id is not None else None
    language = employee.language if employee is not None else "ru"

    audio_bytes = await audio.read()
    try:
        query_text = await speech.recognize(audio_bytes, language)
    except SpeechError as exc:
        logger.error("STT ошибка: %s", exc)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail="Ошибка распознавания речи"
        ) from exc

    wake_word, cleaned = assistant_service.detect_wake_word(query_text)

    # Фолбэк: у сотрудника язык профиля не ru, но говорит он по-русски — «Онви»
    # английской моделью STT не распознаётся. Пробуем русскую модель.
    if require_wake and not wake_word and language != "ru":
        try:
            alt_text = await speech.recognize(audio_bytes, "ru")
        except SpeechError:
            alt_text = ""
        alt_wake, alt_cleaned = assistant_service.detect_wake_word(alt_text)
        if alt_wake:
            query_text, wake_word, cleaned = alt_text, True, alt_cleaned
            language = "ru"  # отвечаем на языке, на котором говорят

    # Постоянное прослушивание: без «Онви» фразу молча пропускаем.
    if require_wake and not wake_word:
        return VoiceAssistantResult(
            query_text=query_text,
            answer_text="",
            found=False,
            matched=[],
            intent="ignored",
        )

    # Если обращения «Онви» нет — всё равно обрабатываем (кнопка нажата осознанно).
    routing_text = cleaned if wake_word else query_text.strip()

    intent = "answer"
    matched: list = []
    found = False
    connect_id: int | None = None
    connect_name: str | None = None
    whole_dept = False

    if not routing_text:
        answer_text = "Слушаю. Что подсказать по товару или с кем соединить?"
    elif assistant_service.is_connect_request(routing_text):
        members = await _department_members(db, employee)
        connect_id, connect_name, whole_dept = assistant_service.resolve_connect_target(
            routing_text, members
        )
        if connect_id is not None:
            intent, answer_text = "connect", f"Соединяю с {connect_name}. Говорите."
        elif whole_dept:
            intent, answer_text = "connect", "Включаю связь со всем отделом. Говорите."
        else:
            answer_text = "Не понял, с кем соединить. Назовите имя коллеги или «весь отдел»."
    else:
        # LLM отвечает на свободный вопрос по данным каталога магазина.
        matched = await assistant_service.retrieve_context(db, routing_text)
        found = bool(matched)
        try:
            answer_text = await llm.answer_over_catalog(routing_text, matched, language)
        except LLMError as exc:
            logger.error("LLM ошибка: %s", exc)
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="Ошибка ассистента") from exc

    try:
        audio_answer = await speech.synthesize(answer_text, language)
    except SpeechError as exc:
        logger.error("TTS ошибка: %s", exc)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="Ошибка синтеза речи") from exc

    # Журнал + геймификация (соединение по рации — вовлечение, но не «ответ найден»).
    db.add(
        AssistantLog(
            employee_id=employee_id,
            query_text=query_text,
            answer_text=answer_text,
            found=found,
        )
    )
    await gamification.award_points(
        db,
        employee_id,
        gamification.POINTS_ASSISTANT_FOUND if found else gamification.POINTS_ASSISTANT_MISS,
    )
    await db.commit()

    return VoiceAssistantResult(
        query_text=query_text,
        answer_text=answer_text,
        found=found,
        matched=matched,
        audio_base64=base64.b64encode(audio_answer).decode("ascii"),
        wake_word=wake_word,
        intent=intent,
        connect_target_id=connect_id,
        connect_target_name=connect_name,
        connect_whole_department=whole_dept,
    )
