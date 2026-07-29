"""kpi and training tables

Цели сотрудникам (kpis) и тесты обучения (tests/test_questions/
test_assignments/test_results) — под кабинеты руководителя и сотрудника
(фронт передан без бэкенда, frontend/src/types.ts: Kpi, Test, TestQuestion).

Данных для сохранения нет — обе группы таблиц новые, backfill не нужен.

Revision ID: c3f7a9d21e48
Revises: 08b96c7016c9
Create Date: 2026-07-29 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3f7a9d21e48"
down_revision: str | Sequence[str] | None = "08b96c7016c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    # --- kpis: цель управляющего сотруднику (metric ограничен тем, что реально
    # считается из assistant_queries/utterances — см. app/db/models/enums.py) ---
    op.create_table(
        "kpis",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("venue_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("metric", sa.String(length=40), nullable=False),
        sa.Column("target", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("period", sa.String(length=10), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("set_by_employee_id", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "metric IN ('dialogs', 'response_sec', 'autonomy', 'help_requests')",
            name="ck_kpis_metric_valid",
        ),
        sa.CheckConstraint("period IN ('day', 'week', 'month')", name="ck_kpis_period_valid"),
        sa.ForeignKeyConstraint(
            ["venue_id"], ["venues.id"], name="fk_kpis_venue_id_venues", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            name="fk_kpis_employee_id_employees",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["set_by_employee_id"],
            ["employees.id"],
            name="fk_kpis_set_by_employee_id_employees",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_kpis"),
    )
    op.create_index("ix_kpis_venue_id", "kpis", ["venue_id"])
    op.create_index("ix_kpis_employee_id", "kpis", ["employee_id"])
    op.create_index("ix_kpis_venue_period_start", "kpis", ["venue_id", "period_start"])
    # Одна активная цель на (сотрудник, метрика, период, окно) — повторная
    # постановка в app/services/kpi.py обновляет эту же строку, не плодит дубликаты.
    op.create_index(
        "ux_kpis_employee_metric_period_start",
        "kpis",
        ["employee_id", "metric", "period", "period_start"],
        unique=True,
    )

    # --- tests: тест для обучения (вопросы приходят готовыми, не генерируются) ---
    op.create_table(
        "tests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("venue_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("source_detail", sa.Text(), nullable=False),
        sa.Column("created_by_employee_id", sa.Integer(), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("pass_score", sa.SmallInteger(), nullable=False),
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
        sa.CheckConstraint(
            "source IN ('errors', 'questions', 'knowledge', 'file', 'prompt')",
            name="ck_tests_source_valid",
        ),
        sa.CheckConstraint("pass_score BETWEEN 0 AND 100", name="ck_tests_pass_score_range"),
        sa.ForeignKeyConstraint(
            ["venue_id"], ["venues.id"], name="fk_tests_venue_id_venues", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_employee_id"],
            ["employees.id"],
            name="fk_tests_created_by_employee_id_employees",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tests"),
    )
    op.create_index("ix_tests_venue_id", "tests", ["venue_id"])

    # --- test_questions: вопросы теста, порядок — position (0-based) ---
    op.create_table(
        "test_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("test_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("correct_index", sa.SmallInteger(), nullable=False),
        sa.Column("explain", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "correct_index >= 0", name="ck_test_questions_correct_index_non_negative"
        ),
        sa.ForeignKeyConstraint(
            ["test_id"], ["tests.id"], name="fk_test_questions_test_id_tests", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("test_id", "position", name="uq_test_questions_test_position"),
        sa.PrimaryKeyConstraint("id", name="pk_test_questions"),
    )
    op.create_index("ix_test_questions_test_id", "test_questions", ["test_id"])

    # --- test_assignments: кому назначен тест ---
    op.create_table(
        "test_assignments",
        sa.Column("test_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("assigned_by_employee_id", sa.Integer(), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["test_id"],
            ["tests.id"],
            name="fk_test_assignments_test_id_tests",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            name="fk_test_assignments_employee_id_employees",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by_employee_id"],
            ["employees.id"],
            name="fk_test_assignments_assigned_by_employee_id_employees",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("test_id", "employee_id", name="pk_test_assignments"),
    )
    op.create_index("ix_test_assignments_employee", "test_assignments", ["employee_id"])

    # --- test_results: один результат на (test, employee) ---
    op.create_table(
        "test_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("test_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("score_percent", sa.SmallInteger(), nullable=False),
        sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "score_percent BETWEEN 0 AND 100", name="ck_test_results_score_percent_range"
        ),
        sa.ForeignKeyConstraint(
            ["test_id"], ["tests.id"], name="fk_test_results_test_id_tests", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            name="fk_test_results_employee_id_employees",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("test_id", "employee_id", name="uq_test_results_test_employee"),
        sa.PrimaryKeyConstraint("id", name="pk_test_results"),
    )
    op.create_index("ix_test_results_test_id", "test_results", ["test_id"])
    op.create_index("ix_test_results_employee", "test_results", ["employee_id"])


def downgrade() -> None:
    """Downgrade schema — обратный порядок относительно зависимостей FK."""
    op.drop_table("test_results")
    op.drop_table("test_assignments")
    op.drop_table("test_questions")
    op.drop_table("tests")
    op.drop_table("kpis")
