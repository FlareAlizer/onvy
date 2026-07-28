"""initial schema

Схема домена чайханы с нуля (specs/pilot-chaihana.md §9): venues, employees,
comm_groups (+ employee_comm_groups), menu_items, stop_list_entries,
utterances, assistant_queries (+ assistant_query_menu_items), metric_snapshots.

Данных для сохранения нет — старый app.db (SQLite, демо-ритейл) выбрасывается
целиком, это не backfill, а первая продовая миграция.

Revision ID: 7430c1b28909
Revises:
Create Date: 2026-07-28 16:52:32.893025

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7430c1b28909"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    # --- venues: точка, единица мультитенантности с первого дня ---
    op.create_table(
        "venues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("default_language", sa.String(length=8), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "default_language IN ('ru', 'uz', 'kk', 'ky', 'en', 'tg')",
            name="ck_venues_default_language_valid",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_venues"),
    )

    # --- employees: PIN-логин, роль, язык. Без биометрии/voice-ID (§2 спеки). ---
    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("venue_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("pin_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "hired_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "role IN ('waiter', 'kitchen', 'bar', 'host', 'manager')",
            name="ck_employees_role_valid",
        ),
        sa.CheckConstraint(
            "language IN ('ru', 'uz', 'kk', 'ky', 'en', 'tg')", name="ck_employees_language_valid"
        ),
        sa.ForeignKeyConstraint(
            ["venue_id"], ["venues.id"], name="fk_employees_venue_id_venues", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_employees"),
    )
    # Фильтр персонала по точке — самый частый запрос над этой таблицей.
    op.create_index("ix_employees_venue_id", "employees", ["venue_id"])

    # --- comm_groups: зал/кухня/бар/все ---
    op.create_table(
        "comm_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("venue_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["venue_id"], ["venues.id"], name="fk_comm_groups_venue_id_venues", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_comm_groups"),
    )
    op.create_index("ix_comm_groups_venue_id", "comm_groups", ["venue_id"])
    # Partial unique: имя группы уникально в рамках живых (не удалённых) групп
    # точки, но допускает повторное имя после мягкого удаления старой записи.
    op.create_index(
        "ux_comm_groups_venue_name_active",
        "comm_groups",
        ["venue_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # --- employee_comm_groups: членство (many-to-many) ---
    op.create_table(
        "employee_comm_groups",
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("comm_group_id", sa.Integer(), nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            name="fk_employee_comm_groups_employee_id_employees",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["comm_group_id"],
            ["comm_groups.id"],
            name="fk_employee_comm_groups_comm_group_id_comm_groups",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("employee_id", "comm_group_id", name="pk_employee_comm_groups"),
    )
    # Обратная сторона членства: "кто в этой группе" (составной PK ведёт с employee_id).
    op.create_index(
        "ix_employee_comm_groups_comm_group_id", "employee_comm_groups", ["comm_group_id"]
    )

    # --- menu_items: техкарта опциональна (NULL = "не заполнено", не "пусто") ---
    op.create_table(
        "menu_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("venue_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("composition", sa.Text(), nullable=True),
        sa.Column("allergens", postgresql.ARRAY(sa.String(length=60)), nullable=True),
        sa.Column("spiciness", sa.SmallInteger(), nullable=True),
        sa.Column("portion_weight_g", sa.Integer(), nullable=True),
        sa.Column("prep_time_minutes", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "spiciness IS NULL OR spiciness BETWEEN 0 AND 3", name="ck_menu_items_spiciness_range"
        ),
        sa.CheckConstraint("price >= 0", name="ck_menu_items_price_non_negative"),
        sa.ForeignKeyConstraint(
            ["venue_id"], ["venues.id"], name="fk_menu_items_venue_id_venues", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_menu_items"),
    )
    op.create_index("ix_menu_items_venue_id", "menu_items", ["venue_id"])
    # Просмотр меню по категориям на точке (экран официанта/управляющего).
    op.create_index("ix_menu_items_venue_category", "menu_items", ["venue_id", "category"])
    op.create_index(
        "ux_menu_items_venue_name_active",
        "menu_items",
        ["venue_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # --- stop_list_entries: живой поток (история), не флаг на menu_item ---
    op.create_table(
        "stop_list_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("venue_id", sa.Integer(), nullable=False),
        sa.Column("menu_item_id", sa.Integer(), nullable=False),
        sa.Column("set_by_employee_id", sa.Integer(), nullable=False),
        sa.Column("unset_by_employee_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "set_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("unset_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["venue_id"],
            ["venues.id"],
            name="fk_stop_list_entries_venue_id_venues",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["menu_item_id"],
            ["menu_items.id"],
            name="fk_stop_list_entries_menu_item_id_menu_items",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["set_by_employee_id"],
            ["employees.id"],
            name="fk_stop_list_entries_set_by_employee_id_employees",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unset_by_employee_id"],
            ["employees.id"],
            name="fk_stop_list_entries_unset_by_employee_id_employees",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stop_list_entries"),
    )
    op.create_index("ix_stop_list_entries_menu_item_id", "stop_list_entries", ["menu_item_id"])
    # S4: активный стоп-лист точки — проверяется на каждый вопрос ассистента
    # про блюдо, самый горячий путь на этой таблице (частичный индекс).
    op.create_index(
        "ix_stop_list_entries_active",
        "stop_list_entries",
        ["venue_id", "menu_item_id"],
        postgresql_where=sa.text("unset_at IS NULL"),
    )
    # История/аналитика пилота: сколько раз и когда точка держала позиции в стопе.
    op.create_index(
        "ix_stop_list_entries_venue_set_at", "stop_list_entries", ["venue_id", "set_at"]
    )

    # --- utterances: реплика рации, оригинал + перевод + метрики стадий (S3) ---
    op.create_table(
        "utterances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("venue_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("recipient_employee_id", sa.Integer(), nullable=True),
        sa.Column("recipient_group_id", sa.Integer(), nullable=True),
        sa.Column("source_language", sa.String(length=8), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("target_language", sa.String(length=8), nullable=False),
        sa.Column("translated_text", sa.Text(), nullable=True),
        sa.Column("translation_failed", sa.Boolean(), nullable=False),
        sa.Column("asr_ms", sa.Integer(), nullable=True),
        sa.Column("translate_ms", sa.Integer(), nullable=True),
        sa.Column("tts_ms", sa.Integer(), nullable=True),
        sa.Column("total_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(recipient_employee_id IS NOT NULL)::int + (recipient_group_id IS NOT NULL)::int = 1",
            name="ck_utterances_single_recipient_kind",
        ),
        sa.CheckConstraint(
            "source_language IN ('ru', 'uz', 'kk', 'ky', 'en', 'tg')",
            name="ck_utterances_source_language_valid",
        ),
        sa.CheckConstraint(
            "target_language IN ('ru', 'uz', 'kk', 'ky', 'en', 'tg')",
            name="ck_utterances_target_language_valid",
        ),
        sa.ForeignKeyConstraint(
            ["venue_id"], ["venues.id"], name="fk_utterances_venue_id_venues", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["sender_id"],
            ["employees.id"],
            name="fk_utterances_sender_id_employees",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_employee_id"],
            ["employees.id"],
            name="fk_utterances_recipient_employee_id_employees",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_group_id"],
            ["comm_groups.id"],
            name="fk_utterances_recipient_group_id_comm_groups",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_utterances"),
    )
    # S6: лента реплик по точке и времени — основной экран управляющего.
    op.create_index("ix_utterances_venue_created", "utterances", ["venue_id", "created_at"])
    # Личная история сотрудника (реплики за смену).
    op.create_index("ix_utterances_sender_created", "utterances", ["sender_id", "created_at"])

    # --- assistant_queries: запрос к ассистенту над меню (S1, S2) ---
    op.create_table(
        "assistant_queries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("venue_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("menu_item_found", sa.Boolean(), nullable=False),
        sa.Column("asr_ms", sa.Integer(), nullable=True),
        sa.Column("llm_ms", sa.Integer(), nullable=True),
        sa.Column("tts_ms", sa.Integer(), nullable=True),
        sa.Column("total_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["venue_id"],
            ["venues.id"],
            name="fk_assistant_queries_venue_id_venues",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            name="fk_assistant_queries_employee_id_employees",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_assistant_queries"),
    )
    # specs/pilot-chaihana.md §9: "запросы сотрудника за смену" — явно из спеки.
    op.create_index(
        "ix_assistant_queries_employee_created", "assistant_queries", ["employee_id", "created_at"]
    )
    op.create_index(
        "ix_assistant_queries_venue_created", "assistant_queries", ["venue_id", "created_at"]
    )

    # --- assistant_query_menu_items: связка вместо ARRAY(Integer) — FK-целостность ---
    op.create_table(
        "assistant_query_menu_items",
        sa.Column("assistant_query_id", sa.Integer(), nullable=False),
        sa.Column("menu_item_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["assistant_query_id"],
            ["assistant_queries.id"],
            name="fk_assistant_query_menu_items_assistant_query_id_assist_d0a3",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["menu_item_id"],
            ["menu_items.id"],
            name="fk_assistant_query_menu_items_menu_item_id_menu_items",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "assistant_query_id", "menu_item_id", name="pk_assistant_query_menu_items"
        ),
    )
    op.create_index(
        "ix_assistant_query_menu_items_menu_item_id", "assistant_query_menu_items", ["menu_item_id"]
    )

    # --- metric_snapshots: дневной срез метрик пилота для CSV (S6, §10) ---
    op.create_table(
        "metric_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("venue_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["venue_id"],
            ["venues.id"],
            name="fk_metric_snapshots_venue_id_venues",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "venue_id", "snapshot_date", name="uq_metric_snapshots_venue_snapshot_date"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_metric_snapshots"),
    )
    op.create_index("ix_metric_snapshots_venue_id", "metric_snapshots", ["venue_id"])


def downgrade() -> None:
    """Downgrade schema — обратный порядок относительно зависимостей FK."""
    op.drop_table("metric_snapshots")
    op.drop_table("assistant_query_menu_items")
    op.drop_table("assistant_queries")
    op.drop_table("utterances")
    op.drop_table("stop_list_entries")
    op.drop_table("menu_items")
    op.drop_table("employee_comm_groups")
    op.drop_table("comm_groups")
    op.drop_table("employees")
    op.drop_table("venues")
