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


def sql_in(column: str, values: tuple[str, ...]) -> str:
    """Собрать текст 'column IN (...)' для CheckConstraint."""
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"
