"""Вход по почте и паролю

Основной способ входа — почта с паролем; быстрый вход по PIN остаётся вторым
(официант в зале держит поднос одной рукой, длинный пароль там неудобен).

Обе колонки NULLABLE и backfill не нужен: у линейного персонала почты может не
быть вовсе, тогда работает только PIN. Уникальность почты — глобальная, а не в
пределах точки: по ней входят, и один адрес не может вести к двум разным людям.

Revision ID: d5a1c8b09f32
Revises: c3f7a9d21e48
Create Date: 2026-07-29 19:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d5a1c8b09f32"
down_revision: str | Sequence[str] | None = "c3f7a9d21e48"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("email", sa.String(length=160), nullable=True))
    op.add_column(
        "employees", sa.Column("password_hash", sa.String(length=255), nullable=True)
    )
    # Индекс частичный: уволенные освобождают адрес, а сотрудники без почты
    # (вход только по PIN) в индекс не попадают вовсе.
    op.create_index(
        "ux_employees_email_active",
        "employees",
        ["email"],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ux_employees_email_active", table_name="employees")
    op.drop_column("employees", "password_hash")
    op.drop_column("employees", "email")
