"""add employee nickname

Короткая кличка сотрудника на смене ("Азиз" при полном имени "Азизбек
Рахматуллаев") — голосовая адресация (app/domain/intents.py, Colleague)
ищет обращение по ней в первую очередь: распознавание в шуме справляется
с кличкой заметно лучше, чем с длинным именем. Обратной совместимости не
нужно: колонка NULLABLE, существующие строки получают NULL (обращение тогда
ищут по первому слову name — см. Colleague.spoken_forms), backfill не нужен.

Revision ID: 08b96c7016c9
Revises: 7430c1b28909
Create Date: 2026-07-28 17:47:39.442226

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "08b96c7016c9"
down_revision: str | Sequence[str] | None = "7430c1b28909"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("nickname", sa.String(length=60), nullable=True))
    # Две одинаковые клички в одной точке делают голосовое обращение лотереей:
    # система не может знать, кого из двоих зовут. Индекс частичный — уволенные
    # (deleted_at) освобождают кличку, а NULL их не занимает вовсе.
    op.create_index(
        "ux_employees_venue_nickname_active",
        "employees",
        ["venue_id", "nickname"],
        unique=True,
        postgresql_where=sa.text("nickname IS NOT NULL AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ux_employees_venue_nickname_active", table_name="employees")
    op.drop_column("employees", "nickname")
