"""Tests for the budget rollup service.

Service is pure-function; no DB or Flask context needed.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.services.budget import days_in_month, rollup_month


def _cats():
    return [
        (1, "Groceries", "#38bdf8", 0, Decimal("600")),
        (2, "Dining", "#facc15", 1, Decimal("200")),
        (3, "Gas", "#4ade80", 2, Decimal("150")),
    ]


def test_days_in_month() -> None:
    assert days_in_month(date(2026, 2, 1)) == 28
    assert days_in_month(date(2024, 2, 1)) == 29
    assert days_in_month(date(2026, 1, 1)) == 31


def test_rollup_sums_per_category_and_total() -> None:
    txns = [
        (1, Decimal("120"), date(2026, 5, 3)),
        (1, Decimal("85"), date(2026, 5, 9)),
        (2, Decimal("40"), date(2026, 5, 6)),
        (3, Decimal("60"), date(2026, 5, 10)),
    ]
    summary = rollup_month(_cats(), txns, date(2026, 5, 15))
    by_id = {c.category_id: c for c in summary.categories}
    assert by_id[1].spent == Decimal("205.00")
    assert by_id[2].spent == Decimal("40.00")
    assert by_id[3].spent == Decimal("60.00")
    assert summary.total_spent == Decimal("305.00")
    assert summary.total_limit == Decimal("950.00")


def test_on_pace_flag_uses_day_of_month() -> None:
    # Mid-month (day 15 of 31) = ~48% elapsed. A category at 30% spent is on pace,
    # one at 80% is over.
    txns = [
        (1, Decimal("180"), date(2026, 5, 5)),  # 30% of $600
        (2, Decimal("160"), date(2026, 5, 5)),  # 80% of $200
    ]
    summary = rollup_month(_cats(), txns, date(2026, 5, 15))
    by_id = {c.category_id: c for c in summary.categories}
    assert by_id[1].on_pace is True
    assert by_id[2].on_pace is False
    assert summary.categories_over_pace == 1


def test_categories_over_pace_skips_zero_limit() -> None:
    # A category with $0 limit shouldn't drag the "over pace" count.
    cats = _cats() + [(4, "Misc", "#888888", 3, Decimal("0"))]
    summary = rollup_month(cats, [], date(2026, 5, 10))
    assert summary.categories_over_pace == 0


def test_percent_spent_can_exceed_100() -> None:
    txns = [(1, Decimal("720"), date(2026, 5, 8))]  # 120% of $600
    summary = rollup_month(_cats(), txns, date(2026, 5, 15))
    by_id = {c.category_id: c for c in summary.categories}
    assert by_id[1].percent_spent > Decimal("100")
    assert by_id[1].on_pace is False


def test_empty_inputs() -> None:
    summary = rollup_month([], [], date(2026, 5, 15))
    assert summary.total_spent == Decimal("0")
    assert summary.total_limit == Decimal("0")
    assert summary.categories == ()


def test_sort_order_respected() -> None:
    cats = [
        (10, "Z last", "#000", 5, Decimal("100")),
        (11, "A first", "#000", 0, Decimal("100")),
        (12, "B second", "#000", 1, Decimal("100")),
    ]
    summary = rollup_month(cats, [], date(2026, 5, 1))
    names = [c.name for c in summary.categories]
    assert names == ["A first", "B second", "Z last"]
