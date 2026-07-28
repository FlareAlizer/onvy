from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.deps import require_api_key
from app.models.employee import Employee
from app.schemas.assistant import AssistantAnswer, AssistantQuery
from app.services import assistant as assistant_service
from app.services import llm
from app.services.llm import LLMError

router = APIRouter(tags=["assistant"], dependencies=[Depends(require_api_key)])


@router.post("/assistant/ask", response_model=AssistantAnswer)
async def ask(payload: AssistantQuery, db: AsyncSession = Depends(get_session)) -> AssistantAnswer:
    """Быстрый поиск по каталогу без LLM (офлайн, для проверки). Голос → см. /voice."""
    matched, found = await assistant_service.answer_query(db, payload.text)
    answer = (
        assistant_service.format_answer(matched[0])
        if found
        else "По этому запросу ничего не нашёл. Уточните название товара."
    )
    return AssistantAnswer(answer=answer, matched=matched, found=found)


@router.post("/assistant/ask-llm", response_model=AssistantAnswer)
async def ask_llm(
    payload: AssistantQuery, db: AsyncSession = Depends(get_session)
) -> AssistantAnswer:
    """Свободный вопрос к LLM по базе знаний магазина (текст → текст).

    Тот же движок, что и голосовой ассистент, но без ASR/TTS — удобно печатать.
    """
    if not settings.yandex_enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM не настроен: заполни YANDEX_API_KEY и YANDEX_FOLDER_ID",
        )
    language = "ru"
    if payload.employee_id is not None:
        employee = await db.get(Employee, payload.employee_id)
        if employee is not None:
            language = employee.language

    matched = await assistant_service.retrieve_context(db, payload.text)
    try:
        answer = await llm.answer_over_catalog(payload.text, matched, language)
    except LLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="Ошибка ассистента") from exc
    return AssistantAnswer(answer=answer, matched=matched, found=bool(matched))
