"""Постфактум-аналитика диалогов: загрузка записи → транскрибация → 2-LLM разбор."""

import json
import logging
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.deps import require_api_key
from app.models.analysis import DialogueAnalysis
from app.models.employee import Employee
from app.schemas.analysis import AnalysisDetail, AnalysisSummary, AnalyzeTextIn, UploadResult
from app.services import analytics, speech
from app.services.speech import SpeechError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analytics"], dependencies=[Depends(require_api_key)])


def _require_yandex() -> None:
    if not settings.yandex_enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Yandex не настроен (YANDEX_API_KEY/YANDEX_FOLDER_ID)",
        )


def _to_detail(row: DialogueAnalysis) -> AnalysisDetail:
    return AnalysisDetail(
        id=row.id,
        employee_id=row.employee_id,
        recording_id=row.recording_id,
        transcript=row.transcript,
        kpi_score=row.kpi_score,
        is_sold=row.is_sold,
        analysis=json.loads(row.analysis_json),
        created_at=row.created_at,
    )


async def _run_pipeline(db: AsyncSession, transcript: str, employee_id: int | None) -> UploadResult:
    """Общий хвост: сегментатор → аналитик → сохранение разборов."""
    recording_id = uuid.uuid4().hex[:12]
    results = await analytics.analyze_recording(transcript)

    rows: list[DialogueAnalysis] = []
    for dialogue_text, analysis in results:
        deal = analysis.get("deal_analysis", {}) or {}
        row = DialogueAnalysis(
            employee_id=employee_id,
            recording_id=recording_id,
            transcript=dialogue_text,
            analysis_json=json.dumps(analysis, ensure_ascii=False),
            kpi_score=int(analysis.get("kpi_score", 0) or 0),
            is_sold=bool(deal.get("is_sold", False)),
        )
        db.add(row)
        rows.append(row)
    await db.commit()
    for row in rows:
        await db.refresh(row)

    return UploadResult(
        recording_id=recording_id,
        transcript=transcript,
        dialogues_found=len(rows),
        analyses=[_to_detail(r) for r in rows],
    )


@router.post("/analytics/upload", response_model=UploadResult)
async def upload_recording(
    audio: UploadFile,
    employee_id: int | None = Form(default=None),
    db: AsyncSession = Depends(get_session),
) -> UploadResult:
    """Запись с микрофона (LPCM 16 kHz) → транскрибация → нарезка → разбор."""
    _require_yandex()

    language = "ru"
    if employee_id is not None:
        employee = await db.get(Employee, employee_id)
        if employee is not None:
            language = employee.language

    audio_bytes = await audio.read()
    try:
        transcript = await speech.recognize_long(audio_bytes, language)
    except SpeechError as exc:
        logger.error("STT ошибка (analytics): %s", exc)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="Ошибка распознавания") from exc

    if not transcript.strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Речь не распознана (тишина)"
        )
    return await _run_pipeline(db, transcript, employee_id)


@router.post("/analytics/analyze-text", response_model=UploadResult)
async def analyze_text(
    payload: AnalyzeTextIn, db: AsyncSession = Depends(get_session)
) -> UploadResult:
    """Разбор готовой транскрибации (без аудио). Тот же конвейер из 2 LLM."""
    _require_yandex()
    return await _run_pipeline(db, payload.text, payload.employee_id)


@router.get("/analytics/analyses", response_model=list[AnalysisSummary])
async def list_analyses(
    employee_id: int | None = None, db: AsyncSession = Depends(get_session)
) -> list[AnalysisSummary]:
    """Список разборов (все — для РОПа, либо по сотруднику)."""
    query = select(DialogueAnalysis).order_by(DialogueAnalysis.id.desc())
    if employee_id is not None:
        query = query.where(DialogueAnalysis.employee_id == employee_id)
    rows = (await db.execute(query)).scalars().all()
    out = []
    for r in rows:
        try:
            summary = json.loads(r.analysis_json).get("summary", "")
        except json.JSONDecodeError:
            summary = ""
        out.append(
            AnalysisSummary(
                id=r.id,
                employee_id=r.employee_id,
                recording_id=r.recording_id,
                kpi_score=r.kpi_score,
                is_sold=r.is_sold,
                summary=summary,
                created_at=r.created_at,
            )
        )
    return out


@router.get("/analytics/analyses/{analysis_id}", response_model=AnalysisDetail)
async def get_analysis(analysis_id: int, db: AsyncSession = Depends(get_session)) -> AnalysisDetail:
    """Полный разбор одного диалога."""
    row = await db.get(DialogueAnalysis, analysis_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Разбор не найден")
    return _to_detail(row)
