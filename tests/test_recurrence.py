"""Tests for the bill / subscription recurrence engine."""

from __future__ import annotations

from datetime import date

import pytest

from app.services.recurrence import advance_due_date, next_occurrences


def test_monthly_occurrences_through_horizon() -> None:
    occ = next_occurrences(date(2026, 1, 15), "monthly", date(2026, 6, 30))
    assert occ == [
        date(2026, 1, 15),
        date(2026, 2, 15),
        date(2026, 3, 15),
        date(2026, 4, 15),
        date(2026, 5, 15),
        date(2026, 6, 15),
    ]


def test_biweekly_occurrences() -> None:
    occ = next_occurrences(date(2026, 1, 1), "biweekly", date(2026, 2, 28))
    assert len(occ) == 5
    assert occ[1] == date(2026, 1, 15)


def test_one_time_returns_single() -> None:
    assert next_occurrences(date(2026, 5, 1), "one_time", date(2026, 12, 31)) == [date(2026, 5, 1)]


def test_start_after_horizon_returns_empty() -> None:
    assert next_occurrences(date(2027, 1, 1), "monthly", date(2026, 12, 31)) == []


def test_unknown_recurrence_raises() -> None:
    with pytest.raises(ValueError):
        next_occurrences(date(2026, 1, 1), "fortnightly", date(2026, 12, 31))


def test_advance_due_date_monthly() -> None:
    assert advance_due_date(date(2026, 1, 31), "monthly") == date(2026, 2, 28)


def test_advance_due_date_quarterly() -> None:
    assert advance_due_date(date(2026, 1, 1), "quarterly") == date(2026, 4, 1)


def test_advance_due_date_annual() -> None:
    assert advance_due_date(date(2026, 5, 1), "annual") == date(2027, 5, 1)


def test_advance_due_date_one_time_returns_same() -> None:
    assert advance_due_date(date(2026, 5, 1), "one_time") == date(2026, 5, 1)


def test_advance_due_date_unknown_raises() -> None:
    with pytest.raises(ValueError):
        advance_due_date(date(2026, 5, 1), "fortnightly")
