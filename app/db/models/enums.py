"""Допустимые значения языков/ролей для CHECK-констрейнтов доменных таблиц.

Сознательно не Postgres ENUM-тип: набор языков/ролей может пополниться в
проде, а `ALTER TYPE ... ADD VALUE` нельзя выполнить внутри транзакции —
ловушка для будущих миграций. CHECK на VARCHAR меняется обычным
`ALTER TABLE ... DROP/ADD CONSTRAINT` в одной транзакционной миграции.
"""

# Полный цикл ASR + перевод + TTS: ru, uz, kk, ky, en (specs/pilot-chaihana.md §2).
# tg (таджикский) — деградация: перевод и озвучка есть, распознавание требует
# ручной проверки, но как язык реплики/сотрудника он всё равно валиден.
LANGUAGES = ("ru", "uz", "kk", "ky", "en", "tg")

EMPLOYEE_ROLES = ("waiter", "kitchen", "bar", "host", "manager")

# Метрики KPI, которые управляющий может назначить сотруднику. Сознательно не
# весь EmployeeStats фронта (frontend/src/types.ts): revenue/avgCheck/conversion/
# scriptCompliance у нас нет источника (нет интеграции с POS) — цель по ним
# нельзя было бы честно посчитать "текущее значение", поэтому в KPI их нет.
# Соответствие каждого ключа расчёту — app/services/stats.py.
KPI_METRICS = ("dialogs", "response_sec", "autonomy", "help_requests")

KPI_PERIODS = ("day", "week", "month")

# Источник теста (Test.source во фронте, frontend/src/types.ts): из каких
# данных управляющий собрал вопросы. Сама генерация вопросов ИИ — не в этом
# лупе, здесь только хранение и назначение готового теста.
TEST_SOURCES = ("errors", "questions", "knowledge", "file", "prompt")


def sql_in(column: str, values: tuple[str, ...]) -> str:
    """Собрать текст 'column IN (...)' для CheckConstraint."""
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"
