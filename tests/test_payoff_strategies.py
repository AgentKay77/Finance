"""Tests for snowball vs avalanche payoff strategies."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.services.payoff_strategies import StrategyLoan, compare_strategies


def _three_loans() -> list[StrategyLoan]:
    """Set up loans where snowball and avalanche pick different first targets.

    - L1: small balance, low rate (snowball picks)
    - L2: medium balance, highest rate (avalanche picks)
    - L3: large balance, mid rate
    """

    base = date(2026, 1, 1)
    return [
        StrategyLoan(
            id=1,
            name="CC small",
            current_balance=Decimal("2000"),
            annual_rate=Decimal("0.10"),
            minimum_payment=Decimal("80"),
            next_payment_date=base,
        ),
        StrategyLoan(
            id=2,
            name="CC big rate",
            current_balance=Decimal("8000"),
            annual_rate=Decimal("0.24"),
            minimum_payment=Decimal("250"),
            next_payment_date=base,
        ),
        StrategyLoan(
            id=3,
            name="Auto",
            current_balance=Decimal("18000"),
            annual_rate=Decimal("0.06"),
            minimum_payment=Decimal("400"),
            next_payment_date=base,
        ),
    ]


def test_no_loans_returns_empty_results() -> None:
    cmp = compare_strategies([], Decimal("100"))
    assert cmp.snowball.months_to_debt_free == 0
    assert cmp.avalanche.total_interest == Decimal("0.00")


def test_snowball_pays_smallest_first() -> None:
    cmp = compare_strategies(_three_loans(), Decimal("300"))
    assert cmp.snowball.payoff_order[0][0] == 1  # smallest balance


def test_avalanche_pays_highest_rate_first() -> None:
    cmp = compare_strategies(_three_loans(), Decimal("300"))
    assert cmp.avalanche.payoff_order[0][0] == 2  # highest rate


def test_extra_budget_shortens_payoff_vs_baseline() -> None:
    cmp = compare_strategies(_three_loans(), Decimal("500"))
    assert cmp.snowball.months_to_debt_free < cmp.baseline.months_to_debt_free
    assert cmp.avalanche.months_to_debt_free < cmp.baseline.months_to_debt_free


def test_avalanche_saves_more_interest_than_snowball_when_spreads_are_wide() -> None:
    cmp = compare_strategies(_three_loans(), Decimal("300"))
    assert cmp.avalanche.total_interest <= cmp.snowball.total_interest


def test_savings_field_populated_relative_to_baseline() -> None:
    cmp = compare_strategies(_three_loans(), Decimal("400"))
    assert cmp.snowball.interest_savings_vs_baseline > Decimal("0")
    assert cmp.avalanche.interest_savings_vs_baseline > Decimal("0")


def test_monthly_balance_total_decreases_to_zero() -> None:
    cmp = compare_strategies(_three_loans(), Decimal("500"))
    totals = [t for _, t in cmp.snowball.monthly_balance_total]
    assert totals[0] > totals[-1]
    assert totals[-1] <= Decimal("0.05")


def test_zero_extra_budget_matches_baseline_payoff() -> None:
    cmp = compare_strategies(_three_loans(), Decimal("0"))
    assert cmp.snowball.months_to_debt_free == cmp.baseline.months_to_debt_free
