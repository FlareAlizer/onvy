"""Позиция меню уникальна в паре «название + раздел», а не по названию

В настоящих меню одно название встречается в нескольких разделах с разной ценой
и выходом: «Чай облепиховый» в чайниках и порционно, «Цезарь» с курицей и с
креветками в разных группах, летнее меню поверх основного. Уникальность по
одному названию превращала это в конфликт — загрузка файла отклоняла строки, и
заведение молча теряло позиции.

Раздел (`category`) NOT NULL DEFAULT '' — NULL в индексе не появляется, и
частичный уникальный индекс работает без coalesce.

Если в точке УЖЕ лежат две активные позиции с одинаковыми названием и разделом
(такого быть не должно — прежний индекс это запрещал), создание индекса упадёт,
и миграция остановится, ничего не испортив.

Revision ID: f2b4e7c15a90
Revises: d5a1c8b09f32
Create Date: 2026-08-15 12:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f2b4e7c15a90"
down_revision: str | Sequence[str] | None = "d5a1c8b09f32"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ux_menu_items_venue_name_category_active",
        "menu_items",
        ["venue_id", "name", "category"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_index("ux_menu_items_venue_name_active", table_name="menu_items")


def downgrade() -> None:
    # Обратный ход возможен только если названия внутри точки не повторяются:
    # позиции, разведённые по разделам, старому индексу противоречат.
    op.create_index(
        "ux_menu_items_venue_name_active",
        "menu_items",
        ["venue_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_index("ux_menu_items_venue_name_category_active", table_name="menu_items")
