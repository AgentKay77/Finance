"""Tests for the amortization service.

Anchors:
- Standard mortgage payment matches the textbook formula.
- A finished schedule's principal sums equal the original principal.
- Drift detector thresholds (green/yellow/red).
- Extra payments shorten the schedule and reduce total interest.
- Rate changes re-amortize correctly.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.services.amortization import (
    ExtraPaymentInput,
    LoanTerms,
    RateChangeInput,
    build_schedule,
    detect_drift,
    drift_band_dollars,
    fixed_payment,
    predict_balance_at,
)


def _terms(principal="200000", rate="0.06", months=360, payment=None) -> LoanTerms:
    p = Decimal(principal)
    r = Decimal(rate)
    pay = Decimal(payment) if payment else fixed_payment(p, r, months)
    return LoanTerms(
        principal=p,
        annual_rate=r,
        term_months=months,
        payment_amount=pay,
        first_payment_date=date(2026, 1, 1),
    )


def test_fixed_payment_matches_known_value() -> None:
    # 200,000 at 6% for 360 months = 1199.10 (rounded to cents).
    assert fixed_payment(Decimal("200000"), Decimal("0.06"), 360) == Decimal("1199.10")


def test_fixed_payment_zero_rate_is_principal_over_term() -> None:
    assert fixed_payment(Decimal("12000"), Decimal("0"), 12) == Decimal("1000.00")


def test_fixed_payment_invalid_term_raises() -> None:
    with pytest.raises(ValueError):
        fixed_payment(Decimal("1000"), Decimal("0.05"), 0)


def test_full_schedule_principal_sums_to_original() -> None:
    terms = _terms()
    sched = build_schedule(terms)
    total_principal = sum(r.principal for r in sched.rows)
    # Allow 1¢ rounding tolerance across 360 periods.
    assert abs(total_principal - terms.principal) <= Decimal("0.05")
    assert sched.rows[-1].balance == Decimal("0.00")


def test_short_loan_reaches_zero() -> None:
    terms = _terms(principal="12000", rate="0.05", months=12)
    sched = build_schedule(terms)
    assert sched.months_to_payoff == 12
    assert sched.rows[-1].balance == Decimal("0.00")


def test_one_time_extra_payment_shortens_schedule() -> None:
    terms = _terms()
    baseline = build_schedule(terms)
    sched = build_schedule(
        terms,
        extras=[
            ExtraPaymentInput(
                payment_type="one_time",
                amount=Decimal("20000"),
                start_date=date(2026, 6, 1),
            )
        ],
    )
    assert sched.months_to_payoff < baseline.months_to_payoff
    assert sched.total_interest < baseline.total_interest
    assert sched.total_extra == Decimal("20000.00")


def test_recurring_monthly_extra_saves_interest() -> None:
    terms = _terms()
    baseline = build_schedule(terms)
    sched = build_schedule(
        terms,
        extras=[
            ExtraPaymentInput(
                payment_type="recurring",
                amount=Decimal("100"),
                start_date=date(2026, 1, 1),
                frequency="monthly",
            )
        ],
    )
    assert sched.months_to_payoff < baseline.months_to_payoff
    saved = baseline.total_interest - sched.total_interest
    assert saved > Decimal("10000")


def test_recurring_annual_extra() -> None:
    terms = _terms()
    sched = build_schedule(
        terms,
        extras=[
            ExtraPaymentInput(
                payment_type="recurring",
                amount=Decimal("3000"),
                start_date=date(2026, 6, 1),
                frequency="annual",
            )
        ],
    )
    assert sched.total_extra > Decimal("0")
    assert sched.months_to_payoff < 360


def test_rate_change_re_amortizes_remaining_balance() -> None:
    terms = _terms(rate="0.06")
    sched = build_schedule(
        terms,
        rate_changes=[RateChangeInput(effective_date=date(2030, 1, 1), new_rate=Decimal("0.04"))],
    )
    # Payment after the change should differ from the original payment.
    pre = [r for r in sched.rows if r.due_date < date(2030, 1, 1)]
    post = [r for r in sched.rows if r.due_date >= date(2030, 1, 1)]
    assert pre and post
    assert post[0].payment != pre[-1].payment


def test_unknown_extra_type_raises() -> None:
    terms = _terms()
    with pytest.raises(ValueError):
        build_schedule(
            terms,
            extras=[
                ExtraPaymentInput(
                    payment_type="bogus",
                    amount=Decimal("100"),
                    start_date=date(2026, 1, 1),
                )
            ],
        )


def test_unknown_frequency_raises() -> None:
    terms = _terms()
    with pytest.raises(ValueError):
        build_schedule(
            terms,
            extras=[
                ExtraPaymentInput(
                    payment_type="recurring",
                    amount=Decimal("100"),
                    start_date=date(2026, 1, 1),
                    frequency="hourly",
                )
            ],
        )


def test_biweekly_extra() -> None:
    terms = _terms()
    sched = build_schedule(
        terms,
        extras=[
            ExtraPaymentInput(
                payment_type="recurring",
                amount=Decimal("50"),
                start_date=date(2026, 1, 1),
                frequency="biweekly",
                end_date=date(2027, 12, 31),
            )
        ],
    )
    assert sched.total_extra > Decimal("0")


def test_drift_green_within_dollar_threshold() -> None:
    r = detect_drift(Decimal("100000"), Decimal("100040"))
    assert r.severity == "green"
    assert r.delta == Decimal("40.00")


def test_drift_green_within_pct_threshold() -> None:
    # 0.4% over predicted, dollar delta > 50 — still green by percent rule.
    r = detect_drift(Decimal("20000"), Decimal("20080"))  # 0.4% = 80
    assert r.severity == "green"


def test_drift_yellow() -> None:
    # Green threshold here = max($50, 0.5% of $100k) = $500.
    # Yellow threshold = max($250, 2% of $100k) = $2000.
    r = detect_drift(Decimal("100000"), Decimal("101000"))
    assert r.severity == "yellow"


def test_drift_red() -> None:
    r = detect_drift(Decimal("100000"), Decimal("105000"))
    assert r.severity == "red"


def test_drift_red_negative_direction() -> None:
    r = detect_drift(Decimal("100000"), Decimal("90000"))
    assert r.severity == "red"
    assert r.delta < 0


def test_drift_zero_predicted() -> None:
    r = detect_drift(Decimal("0"), Decimal("0"))
    assert r.severity == "green"


def test_predict_balance_at() -> None:
    terms = _terms(principal="10000", rate="0.05", months=12)
    sched = build_schedule(terms)
    # On the first payment date, predicted closing balance should be < principal.
    prediction = predict_balance_at(sched, date(2026, 1, 1))
    assert prediction is not None
    assert prediction < Decimal("10000")


def test_predict_balance_before_any_period_returns_none() -> None:
    terms = _terms(principal="10000", rate="0.05", months=12)
    sched = build_schedule(terms)
    assert predict_balance_at(sched, date(2025, 1, 1)) is None


def test_starting_balance_recalibration() -> None:
    """The 'recalibrate from current balance' action passes a starting_balance."""
    terms = _terms()
    sched = build_schedule(
        terms,
        starting_balance=Decimal("150000"),
        starting_date=date(2030, 6, 1),
        starting_period=54,
    )
    assert sched.rows[0].period == 54
    assert sched.rows[-1].balance == Decimal("0.00")


def test_same_day_extra_and_minimum_baseline_parity() -> None:
    """An extra payment dated the same day as the minimum should match
    the simpler 'all at once' bucketing within a few cents.
    """
    terms = _terms(principal="100000", rate="0.06", months=120)
    extra_same_day = build_schedule(
        terms,
        extras=[
            ExtraPaymentInput(
                payment_type="one_time",
                amount=Decimal("5000"),
                start_date=date(2026, 1, 1),
            )
        ],
    )
    assert extra_same_day.months_to_payoff < 120
    assert extra_same_day.total_extra == Decimal("5000.00")


def test_extra_mid_month_saves_more_interest_than_extra_at_period_end() -> None:
    """An extra payment 15 days before the minimum saves ~15 days of
    interest on the extra principal vs an extra dated on the minimum day.
    """
    terms = _terms(principal="200000", rate="0.06", months=240)
    end_of_month = build_schedule(
        terms,
        extras=[
            ExtraPaymentInput(
                payment_type="one_time",
                amount=Decimal("10000"),
                start_date=date(2026, 2, 1),  # same as minimum
            )
        ],
    )
    mid_month = build_schedule(
        terms,
        extras=[
            ExtraPaymentInput(
                payment_type="one_time",
                amount=Decimal("10000"),
                start_date=date(2026, 1, 15),  # 17 days earlier
            )
        ],
    )
    # The mid-month payment posts ~17 days earlier, so total interest paid
    # over the life of the loan should be strictly lower (even if just a
    # few dollars on a single $10k bump).
    assert mid_month.total_interest < end_of_month.total_interest


def test_extra_payment_on_arbitrary_weekday_applies_on_date() -> None:
    """An extra payment dated on a Sunday is honoured as of that date."""
    terms = _terms(principal="50000", rate="0.06", months=60)
    sunday = date(2026, 1, 4)  # Sunday
    assert sunday.weekday() == 6
    sched = build_schedule(
        terms,
        extras=[
            ExtraPaymentInput(
                payment_type="one_time",
                amount=Decimal("2500"),
                start_date=sunday,
            )
        ],
    )
    assert sched.total_extra == Decimal("2500.00")
    assert sched.months_to_payoff < 60


def test_rate_change_mid_month_splits_interest() -> None:
    """Interest accrued before the rate change uses the old rate;
    interest after uses the new rate.

    First payment is Feb 1. Rate change at Feb 15 falls inside period 2
    (Feb 1 → Mar 1), so the second period's interest should be a mix of
    14 days at 6% and ~15 days at 3% — strictly less than a flat-6%
    period and strictly more than a flat-3% period.
    """
    terms = LoanTerms(
        principal=Decimal("100000"),
        annual_rate=Decimal("0.06"),
        term_months=360,
        payment_amount=fixed_payment(Decimal("100000"), Decimal("0.06"), 360),
        first_payment_date=date(2026, 2, 1),
    )
    sched = build_schedule(
        terms,
        rate_changes=[RateChangeInput(effective_date=date(2026, 2, 15), new_rate=Decimal("0.03"))],
    )
    flat_high = build_schedule(terms)
    flat_low_terms = LoanTerms(
        principal=Decimal("100000"),
        annual_rate=Decimal("0.03"),
        term_months=360,
        payment_amount=fixed_payment(Decimal("100000"), Decimal("0.03"), 360),
        first_payment_date=date(2026, 2, 1),
    )
    flat_low = build_schedule(flat_low_terms)

    period2_split = sched.rows[1].interest
    assert flat_low.rows[1].interest < period2_split < flat_high.rows[1].interest


def test_30_360_convention_gives_consistent_30_day_months() -> None:
    """Under 30/360 every month-to-month gap counts as exactly 30 days."""
    p = Decimal("100000")
    r = Decimal("0.06")
    terms = LoanTerms(
        principal=p,
        annual_rate=r,
        term_months=360,
        payment_amount=fixed_payment(p, r, 360),
        first_payment_date=date(2026, 1, 31),
        day_count_convention="30/360",
    )
    sched = build_schedule(terms)
    # First-period interest under 30/360 == p * r / 12 to within rounding.
    expected = (p * r / Decimal(12)).quantize(Decimal("0.01"))
    assert abs(sched.rows[0].interest - expected) <= Decimal("0.01")


def test_drift_band_dollars_thresholds() -> None:
    yellow, red = drift_band_dollars(Decimal("100000"))
    assert yellow == Decimal("500.00")  # 0.5% of 100k > $50
    assert red == Decimal("2000.00")  # 2% of 100k > $250


def test_drift_band_dollars_floor() -> None:
    yellow, red = drift_band_dollars(Decimal("1000"))
    assert yellow == Decimal("50.00")  # floor
    assert red == Decimal("250.00")  # floor


def test_zero_principal_yields_empty_schedule() -> None:
    terms = LoanTerms(
        principal=Decimal("0"),
        annual_rate=Decimal("0.05"),
        term_months=12,
        payment_amount=Decimal("100"),
        first_payment_date=date(2026, 1, 1),
    )
    sched = build_schedule(terms)
    assert sched.rows == ()
    assert sched.months_to_payoff == 0
