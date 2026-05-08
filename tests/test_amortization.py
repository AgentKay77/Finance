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
