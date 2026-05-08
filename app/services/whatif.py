"""Payoff what-if scenarios (Phase 5).

Built on top of the amortization service. Each scenario is described by
an extra budget plus optional rate-change overrides; the service returns
delta metrics versus the loan's baseline schedule (no extras, current
rate held flat).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.services.amortization import (
    ZERO,
    ExtraPaymentInput,
    LoanTerms,
    RateChangeInput,
    Schedule,
    _q,
    build_schedule,
)


@dataclass(frozen=True)
class WhatIfScenario:
    label: str
    extra_monthly: Decimal = ZERO
    one_time_amount: Decimal = ZERO
    one_time_date: date | None = None
    rate_override: Decimal | None = None
    rate_override_date: date | None = None


@dataclass(frozen=True)
class WhatIfResult:
    label: str
    schedule: Schedule
    months_saved: int
    interest_saved: Decimal
    total_paid_delta: Decimal


def run_scenario(terms: LoanTerms, baseline: Schedule, scenario: WhatIfScenario) -> WhatIfResult:
    extras: list[ExtraPaymentInput] = []
    if scenario.extra_monthly > ZERO:
        extras.append(
            ExtraPaymentInput(
                payment_type="recurring",
                amount=scenario.extra_monthly,
                start_date=terms.first_payment_date,
                frequency="monthly",
            )
        )
    if scenario.one_time_amount > ZERO and scenario.one_time_date is not None:
        extras.append(
            ExtraPaymentInput(
                payment_type="one_time",
                amount=scenario.one_time_amount,
                start_date=scenario.one_time_date,
            )
        )

    rate_changes: list[RateChangeInput] = []
    if scenario.rate_override is not None and scenario.rate_override_date is not None:
        rate_changes.append(
            RateChangeInput(
                effective_date=scenario.rate_override_date,
                new_rate=scenario.rate_override,
            )
        )

    schedule = build_schedule(terms, extras, rate_changes)
    return WhatIfResult(
        label=scenario.label,
        schedule=schedule,
        months_saved=baseline.months_to_payoff - schedule.months_to_payoff,
        interest_saved=_q(baseline.total_interest - schedule.total_interest),
        total_paid_delta=_q(schedule.total_paid - baseline.total_paid),
    )


__all__ = ["WhatIfResult", "WhatIfScenario", "run_scenario"]
