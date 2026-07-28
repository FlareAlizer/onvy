"""Постфактум-аналитика разговоров с покупателями (перенос из прошлой версии).

Конвейер из двух LLM с разными мастер-промптами:
1. СЕГМЕНТАТОР — получает сплошную транскрибацию записи (микрофон включён
   постоянно) и режет её на отдельные диалоги с покупателями, отбрасывая шум.
2. АНАЛИТИК — разбирает каждый диалог: KPI, роли, этапы скрипта, сильные/слабые
   стороны, ошибки с исправлениями, факт сделки.

При ошибке LLM возвращаются безопасные заглушки — фронт не падает.
"""

import logging

from app.services import llm

logger = logging.getLogger(__name__)

# --- LLM №1: сегментатор записи на диалоги ---

_SPLITTER_PROMPT = """
Ты — модуль сегментации аудиозаписей торгового зала. На вход подаётся сплошная
транскрибация записи с микрофона продавца за период работы (микрофон включён
постоянно, поэтому в тексте могут быть обрывки, посторонние разговоры и тишина).

Твоя задача:
1. Найди в тексте ОТДЕЛЬНЫЕ диалоги продавца с покупателями (диалог = связная
   беседа с одним клиентом от приветствия/вопроса до завершения).
2. Отбрось всё, что диалогом не является (разговоры с коллегами, обрывки, шум).
3. Верни диалоги в исходных формулировках, ничего не выдумывая и не дополняя.

Верни СТРОГО JSON без пояснений:
{"dialogues": ["полный текст диалога 1", "полный текст диалога 2", ...]}
Если диалогов нет — {"dialogues": []}.
"""

# --- LLM №2: аналитик диалога (мастер-промпт из прошлой версии проекта) ---

_ANALYZER_PROMPT = """
Ты — профессиональный аналитик качества продаж, психолог и бизнес-тренер (РОП).
Твоя задача — проанализировать «сырой» транскрипт диалога продавца с покупателем.

ВАЖНО: исходный текст сплошной. Логически разметь его по ролям (Сотрудник / Клиент):
приветствие, презентация товара, отработка возражений, закрытие сделки — это
«Сотрудник»; вопросы о цене, сомнения («Дорого», «Подумаю»), короткие ответы — чаще «Клиент».

Проанализируй:
1. Соблюдение этапов продаж (Приветствие, Выявление потребностей, Презентация,
   Работа с возражениями, Закрытие сделки).
2. Слова-паразиты и эмоциональный окрас.
3. Конкретные сильные и слабые стороны.
4. Состоялась ли продажа (слова «беру», «оплачиваю», «оформляем», «карта», «чек»);
   сумму сделки из текста (если продажа есть, а сумма не названа — 0).
5. Критические ошибки: для каждой напиши FIX — прямую речь, как НУЖНО было сказать.

Верни результат СТРОГО в формате JSON (без markdown-обёрток):
{
  "summary": "краткое содержание диалога",
  "kpi_score": число 0-100,
  "deal_analysis": {"is_sold": true/false, "detected_amount": число},
  "sentiment": {"positive": число, "neutral": число, "negative": число},
  "filler_words": [{"word": "слово", "count": число}],
  "script_compliance": [
    {"label": "Приветствие", "status": "success|warning|fail"},
    {"label": "Выявление потребностей", "status": "success|warning|fail"},
    {"label": "Презентация", "status": "success|warning|fail"},
    {"label": "Работа с возражениями", "status": "success|warning|fail"},
    {"label": "Закрытие сделки", "status": "success|warning|fail"}
  ],
  "strengths": ["конкретный пункт (минимум 2)"],
  "weaknesses": ["конкретная ошибка (минимум 2)"],
  "mistakes_and_fixes": [{"error": "что сделал не так", "fix": "как надо было сказать"}],
  "recommendations": ["совет (минимум 2)"],
  "transcript_parsed": [
    {"time": "00:00", "speaker": "Сотрудник|Клиент", "text": "реплика", "tags": []}
  ]
}
"""


def _fallback_analysis(transcript: str, reason: str) -> dict:
    """Заглушка при ошибке аналитика — чтобы интерфейс не ломался."""
    return {
        "summary": "Не удалось получить разбор от нейросети.",
        "kpi_score": 0,
        "deal_analysis": {"is_sold": False, "detected_amount": 0},
        "sentiment": {"positive": 0, "neutral": 100, "negative": 0},
        "filler_words": [],
        "script_compliance": [],
        "strengths": [],
        "weaknesses": [reason],
        "mistakes_and_fixes": [],
        "recommendations": [],
        "transcript_parsed": [
            {"time": "00:00", "speaker": "System", "text": transcript, "tags": []}
        ],
    }


async def split_dialogues(transcript: str) -> list[str]:
    """LLM №1: нарезать сплошную транскрибацию на отдельные диалоги.

    При ошибке сегментатора считаем всю запись одним диалогом (лучше разобрать
    целиком, чем потерять).
    """
    if not transcript.strip():
        return []
    try:
        data = await llm.complete_json(
            _SPLITTER_PROMPT, transcript, temperature=0.1, max_tokens=8000
        )
        dialogues = [d for d in data.get("dialogues", []) if isinstance(d, str) and d.strip()]
        return dialogues if dialogues else [transcript]
    except llm.LLMError as exc:
        logger.warning("Сегментатор не сработал (%s) — берём запись целиком", exc)
        return [transcript]


async def analyze_dialogue(dialogue: str) -> dict:
    """LLM №2: глубокий разбор одного диалога."""
    try:
        return await llm.complete_json(
            _ANALYZER_PROMPT,
            f"Транскрипт для анализа:\n{dialogue}",
            temperature=0.3,
            max_tokens=8000,
        )
    except llm.LLMError as exc:
        logger.error("Аналитик не сработал: %s", exc)
        return _fallback_analysis(dialogue, f"Ошибка анализа: {exc}")


async def analyze_recording(transcript: str) -> list[tuple[str, dict]]:
    """Полный конвейер: сегментатор → аналитик по каждому диалогу.

    Возвращает список пар (текст диалога, разбор).
    """
    dialogues = await split_dialogues(transcript)
    results: list[tuple[str, dict]] = []
    for dialogue in dialogues:
        results.append((dialogue, await analyze_dialogue(dialogue)))
    return results
