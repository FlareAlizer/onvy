"""Юнит-тесты чистой логики app/services/stats.py — без БД, реально прогоняются
на этой машине (нет Docker/Postgres, см. tests/conftest.py). DB-обёртки той же
модели (employee_stats, employee_shifts, faq_rows) не покрыты здесь — им нужна
настоящая сессия, см. tests/test_kpi.py / tests/test_training.py needs_db.
"""

from datetime import UTC, date, datetime

import pytest

from app.services import stats

# --- period_bounds ---------------------------------------------------------------


def test_period_bounds_day_is_the_date_itself() -> None:
    start, end = stats.period_bounds("day", date(2026, 7, 29))
    assert start == end == date(2026, 7, 29)


def test_period_bounds_week_is_monday_to_sunday() -> None:
    # 2026-07-29 — среда.
    start, end = stats.period_bounds("week", date(2026, 7, 29))
    assert start == date(2026, 7, 27)  # понедельник
    assert end == date(2026, 8, 2)  # воскресенье


def test_period_bounds_month_handles_december_rollover() -> None:
    start, end = stats.period_bounds("month", date(2026, 12, 15))
    assert start == date(2026, 12, 1)
    assert end == date(2026, 12, 31)


def test_period_bounds_month_regular() -> None:
    start, end = stats.period_bounds("month", date(2026, 2, 10))
    assert start == date(2026, 2, 1)
    assert end == date(2026, 2, 28)


def test_period_bounds_unknown_period_raises() -> None:
    with pytest.raises(ValueError):
        stats.period_bounds("year", date(2026, 1, 1))


# --- kpi_progress_percent ----------------------------------------------------------


def test_kpi_progress_percent_normal() -> None:
    assert stats.kpi_progress_percent(50, 100) == 50.0


def test_kpi_progress_percent_over_target() -> None:
    assert stats.kpi_progress_percent(150, 100) == 150.0


def test_kpi_progress_percent_zero_target_and_zero_current_is_done() -> None:
    assert stats.kpi_progress_percent(0, 0) == 100.0


def test_kpi_progress_percent_zero_target_nonzero_current_is_undefined() -> None:
    assert stats.kpi_progress_percent(5, 0) is None


# --- autonomy_percent / avg_response_seconds ---------------------------------------


def test_autonomy_percent_no_queries_is_none() -> None:
    assert stats.autonomy_percent(0, 0) is None


def test_autonomy_percent_computes_share() -> None:
    assert stats.autonomy_percent(4, 3) == 75.0


def test_avg_response_seconds_ignores_missing_values() -> None:
    assert stats.avg_response_seconds([1000, None, 3000]) == 2.0


def test_avg_response_seconds_empty_is_none() -> None:
    assert stats.avg_response_seconds([]) is None
    assert stats.avg_response_seconds([None, None]) is None


# --- compute_employee_stats ---------------------------------------------------------


def test_compute_employee_stats_combines_queries_and_utterances() -> None:
    result = stats.compute_employee_stats(
        employee_id=1,
        period_days=7,
        query_total_ms=[1000, 2000],
        query_found=[True, False],
        utterance_total_ms=[500],
        help_request_count=1,
    )
    assert result.dialogs == 3
    assert result.autonomy_percent == 50.0
    assert result.help_requests == 1
    assert result.response_sec == round((1000 + 2000 + 500) / 3 / 1000, 2)


def test_compute_employee_stats_mismatched_lengths_raises() -> None:
    with pytest.raises(ValueError):
        stats.compute_employee_stats(
            employee_id=1,
            period_days=7,
            query_total_ms=[1000],
            query_found=[True, False],
            utterance_total_ms=[],
            help_request_count=0,
        )


def test_compute_employee_stats_no_data_is_honestly_empty() -> None:
    result = stats.compute_employee_stats(
        employee_id=1,
        period_days=7,
        query_total_ms=[],
        query_found=[],
        utterance_total_ms=[],
        help_request_count=0,
    )
    assert result.dialogs == 0
    assert result.autonomy_percent is None  # не 0% — вопросов не было вовсе
    assert result.response_sec is None


# --- group_events_into_shifts -------------------------------------------------------


def _event(
    kind: str,
    at: datetime,
    *,
    total_ms: int | None = 1000,
    is_help_request: bool = False,
    menu_item_found: bool | None = None,
) -> stats.ShiftEvent:
    return stats.ShiftEvent(
        kind=kind,
        at=at,
        text="текст",
        detail=None,
        total_ms=total_ms,
        menu_item_found=menu_item_found,
        is_help_request=is_help_request,
    )


def test_group_events_into_shifts_groups_by_calendar_date() -> None:
    events = [
        _event("utterance", datetime(2026, 7, 28, 10, 0, tzinfo=UTC)),
        _event("assistant_query", datetime(2026, 7, 28, 12, 0, tzinfo=UTC)),
        _event("utterance", datetime(2026, 7, 29, 9, 0, tzinfo=UTC), is_help_request=True),
    ]
    shifts = stats.group_events_into_shifts(events, employee_id=42)

    assert [s.shift_date for s in shifts] == [date(2026, 7, 29), date(2026, 7, 28)]  # новые впереди
    newest, oldest = shifts
    assert newest.employee_id == 42
    assert newest.utterances_count == 1
    assert newest.help_requests == 1
    assert oldest.utterances_count == 1
    assert oldest.assistant_queries_count == 1
    assert oldest.started_at == datetime(2026, 7, 28, 10, 0, tzinfo=UTC)
    assert oldest.ended_at == datetime(2026, 7, 28, 12, 0, tzinfo=UTC)


def test_group_events_into_shifts_empty_input() -> None:
    assert stats.group_events_into_shifts([], employee_id=1) == []


# --- FAQ: normalize/aggregate --------------------------------------------------------


def test_normalize_query_text_collapses_case_and_whitespace() -> None:
    assert stats.normalize_query_text("  Что   в  Лагмане? ") == "что в лагмане?"


def _faq_row(
    text: str, *, found: bool, at: datetime, total_ms: int | None = 1000
) -> stats.FaqQuestionRow:
    return stats.FaqQuestionRow(
        query_text=text, menu_item_found=found, total_ms=total_ms, created_at=at
    )


def test_aggregate_top_questions_groups_and_sorts_by_count() -> None:
    now = datetime(2026, 7, 29, tzinfo=UTC)
    rows = [
        _faq_row("Что в лагмане", found=True, at=now),
        _faq_row("  что   в лагмане ", found=True, at=now),
        _faq_row("есть орехи в плове", found=False, at=now),
    ]
    top = stats.aggregate_top_questions(rows, now=now)
    assert top[0].question == "что в лагмане"
    assert top[0].count == 2
    assert top[0].ever_answered is True
    assert top[1].count == 1


def test_aggregate_top_questions_trend_none_without_previous_window() -> None:
    now = datetime(2026, 7, 29, tzinfo=UTC)
    rows = [_faq_row("вопрос", found=True, at=now)]
    top = stats.aggregate_top_questions(rows, now=now, trend_window_days=7)
    assert top[0].trend_percent is None


def test_aggregate_top_questions_trend_computed_when_previous_exists() -> None:
    now = datetime(2026, 7, 29, tzinfo=UTC)
    recent = now  # эта неделя (>= now - 7d)
    previous = now.replace(day=18)  # прошлая неделя: [now - 14d, now - 7d)
    rows = [
        _faq_row("вопрос", found=True, at=recent),
        _faq_row("вопрос", found=True, at=recent),
        _faq_row("вопрос", found=True, at=previous),
    ]
    top = stats.aggregate_top_questions(rows, now=now, trend_window_days=7)
    assert top[0].trend_percent == 100.0  # было 1, стало 2 -> +100%


def test_aggregate_gaps_only_includes_missed_and_sorts_by_miss_count() -> None:
    now = datetime(2026, 7, 29, tzinfo=UTC)
    rows = [
        _faq_row("аллергия на орехи", found=False, at=now),
        _faq_row("Аллергия на орехи", found=False, at=now),
        _faq_row("что в лагмане", found=True, at=now),
        _faq_row("время готовки шашлыка", found=False, at=now),
    ]
    gaps = stats.aggregate_gaps(rows)
    assert [g.question for g in gaps] == ["аллергия на орехи", "время готовки шашлыка"]
    assert gaps[0].miss_count == 2


def test_aggregate_gaps_ignores_answered_questions() -> None:
    now = datetime(2026, 7, 29, tzinfo=UTC)
    rows = [_faq_row("что в лагмане", found=True, at=now)]
    assert stats.aggregate_gaps(rows) == []


# --- score_test ------------------------------------------------------------------


def test_score_test_all_correct() -> None:
    assert stats.score_test([0, 1, 2], [0, 1, 2]) == 100


def test_score_test_partial() -> None:
    assert stats.score_test([0, 1], [0, 0]) == 50


def test_score_test_none_correct() -> None:
    assert stats.score_test([1, 1], [0, 0]) == 0


def test_score_test_mismatched_length_raises() -> None:
    with pytest.raises(ValueError):
        stats.score_test([0, 1], [0])


def test_score_test_no_questions_is_zero() -> None:
    assert stats.score_test([], []) == 0
