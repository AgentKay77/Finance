"""Tests for payoff what-if scenarios."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.services.amortization import LoanTerms, build_schedule, fixed_payment
from app.services.whatif import WhatIfScenario, run_scenario


def _terms() -> LoanTerms:
    p = Decimal("250000")
    r = Decimal("0.065")
    pay = fixed_payment(p, r, 360)
    return LoanTerms(
        principal=p,
        annual_rate=r,
        term_months=360,
        payment_amount=pay,
        first_payment_date=date(2026, 1, 1),
    )


def test_extra_monthly_saves_months_and_interest() -> None:
    terms = _terms()
    baseline = build_schedule(terms)
    result = run_scenario(
        terms,
        baseline,
        WhatIfScenario(label="+$200/mo", extra_monthly=Decimal("200")),
    )
    assert result.months_saved > 0
    assert result.interest_saved > Decimal("10000")


def test_one_time_lump_saves_interest() -> None:
    terms = _terms()
    baseline = build_schedule(terms)
    result = run_scenario(
        terms,
        baseline,
        WhatIfScenario(
            label="$25k year 3",
            one_time_amount=Decimal("25000"),
            one_time_date=date(2029, 1, 1),
        ),
    )
    assert result.interest_saved > Decimal("0")


def test_rate_drop_lowers_total_paid() -> None:
    terms = _terms()
    baseline = build_schedule(terms)
    result = run_scenario(
        terms,
        baseline,
        WhatIfScenario(
            label="refi to 4.5% next year",
            rate_override=Decimal("0.045"),
            rate_override_date=date(2027, 1, 1),
        ),
    )
    assert result.schedule.total_interest < baseline.total_interest
