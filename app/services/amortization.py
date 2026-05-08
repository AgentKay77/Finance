"""Pure-function amortization service (Phase 2).

Given a loan's terms, its extra payments, and any rate changes, build the
full month-by-month payoff schedule. The module is intentionally
side-effect-free: no DB access, no Flask context, no logging of monetary
values. The Phase 5 what-if scenario tool calls this in a tight loop, so
we keep the hot path allocation-light.

Money is :class:`decimal.Decimal` throughout. Half-up rounding to cents
is applied at every period boundary so accumulated drift is bounded.

Standard fixed-rate amortization formula::

    M = P * (r(1+r)^n) / ((1+r)^n - 1)

where ``r`` is the monthly interest rate (APR / 12) and ``n`` is the
remaining term in months.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
ZERO = Decimal("0")
MAX_PERIODS = 1200  # 100 years — guard against runaway loops on bad input.


def _q(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class LoanTerms:
    """Inputs to the amortization service.

    Attributes mirror :class:`app.models.loan.Loan` columns but are
    primitive types so the service has no SQLAlchemy dependency.
    """

    principal: Decimal
    annual_rate: Decimal  # APR as decimal, e.g. Decimal("0.06375")
    term_months: int
    payment_amount: Decimal
    first_payment_date: date


@dataclass(frozen=True)
class ExtraPaymentInput:
    payment_type: str  # "one_time" or "recurring"
    amount: Decimal
    start_date: date
    end_date: date | None = None
    frequency: str | None = None  # "monthly" | "biweekly" | "annual"


@dataclass(frozen=True)
class RateChangeInput:
    effective_date: date
    new_rate: Decimal


@dataclass(frozen=True)
class PeriodRow:
    period: int
    due_date: date
    payment: Decimal
    principal: Decimal
    interest: Decimal
    extra: Decimal
    balance: Decimal


@dataclass(frozen=True)
class Schedule:
    rows: tuple[PeriodRow, ...]
    payoff_date: date | None
    total_interest: Decimal
    total_principal: Decimal
    total_paid: Decimal
    total_extra: Decimal
    months_to_payoff: int
    months_saved_vs_baseline: int = 0


def _add_months(d: date, months: int) -> date:
    """Naive month math that clamps to month length (handles 31 → Feb)."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    # Clamp day to last day of target month.
    last_day_by_month = (
        31,
        29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    )
    day = min(d.day, last_day_by_month[month - 1])
    return date(year, month, day)


def fixed_payment(principal: Decimal, annual_rate: Decimal, term_months: int) -> Decimal:
    """Return the standard amortizing payment for a fixed-rate loan.

    Used by both the schedule builder (when re-amortizing after a rate
    change) and the what-if module (Phase 5).
    """

    if term_months <= 0:
        raise ValueError("term_months must be positive")
    if principal <= 0:
        return ZERO
    monthly = annual_rate / Decimal(12)
    if monthly == 0:
        return _q(principal / Decimal(term_months))
    one_plus_r_n = (Decimal(1) + monthly) ** term_months
    payment = principal * (monthly * one_plus_r_n) / (one_plus_r_n - Decimal(1))
    return _q(payment)


def _expand_extra_payments(
    extras: Iterable[ExtraPaymentInput], horizon_end: date
) -> dict[tuple[int, int], Decimal]:
    """Flatten extras into a {(year, month): total_extra} map.

    Recurring extras spawn one entry per occurrence within the horizon.
    Multiple extras targeting the same month sum.
    """

    out: dict[tuple[int, int], Decimal] = {}

    def _add(d: date, amount: Decimal) -> None:
        key = (d.year, d.month)
        out[key] = out.get(key, ZERO) + amount

    for ep in extras:
        if ep.payment_type == "one_time":
            _add(ep.start_date, ep.amount)
            continue
        if ep.payment_type != "recurring":
            raise ValueError(f"Unknown extra payment_type: {ep.payment_type!r}")
        end = ep.end_date or horizon_end
        cursor = ep.start_date
        # Cap recurrence iterations defensively.
        for _ in range(MAX_PERIODS * 2):
            if cursor > end:
                break
            _add(cursor, ep.amount)
            if ep.frequency == "monthly":
                cursor = _add_months(cursor, 1)
            elif ep.frequency == "biweekly":
                cursor = cursor + timedelta(days=14)
            elif ep.frequency == "annual":
                cursor = _add_months(cursor, 12)
            else:
                raise ValueError(f"Unknown frequency: {ep.frequency!r}")
    return out


def _rate_for(period_date: date, base_rate: Decimal, changes: list[RateChangeInput]) -> Decimal:
    """Return the effective annual rate for a given period."""
    rate = base_rate
    for rc in changes:
        if rc.effective_date <= period_date:
            rate = rc.new_rate
    return rate


def build_schedule(
    terms: LoanTerms,
    extras: Iterable[ExtraPaymentInput] = (),
    rate_changes: Iterable[RateChangeInput] = (),
    *,
    starting_balance: Decimal | None = None,
    starting_date: date | None = None,
    starting_period: int = 1,
) -> Schedule:
    """Build the full amortization schedule.

    ``starting_balance`` and ``starting_date`` let the drift-detector
    re-amortize from an observed balance without rebuilding from scratch.
    """

    sorted_changes = sorted(rate_changes, key=lambda r: r.effective_date)
    horizon_guess = _add_months(terms.first_payment_date, terms.term_months + 60)
    extras_map = _expand_extra_payments(extras, horizon_guess)

    balance = _q(starting_balance if starting_balance is not None else terms.principal)
    payment_date = starting_date or terms.first_payment_date
    payment = terms.payment_amount

    current_rate = terms.annual_rate
    rows: list[PeriodRow] = []
    total_interest = ZERO
    total_extra = ZERO

    period = starting_period
    while balance > ZERO and period < MAX_PERIODS + starting_period:
        # Re-amortize when crossing a rate change boundary.
        new_rate = _rate_for(payment_date, terms.annual_rate, sorted_changes)
        if new_rate != current_rate:
            remaining_term = max(1, terms.term_months - (period - 1))
            payment = fixed_payment(balance, new_rate, remaining_term)
            current_rate = new_rate

        monthly_rate = current_rate / Decimal(12)
        interest = _q(balance * monthly_rate)
        scheduled_principal = payment - interest
        if scheduled_principal < ZERO:
            scheduled_principal = ZERO  # interest-only edge

        # Final period: settle exactly.
        if scheduled_principal >= balance:
            scheduled_principal = balance
            payment_actual = _q(scheduled_principal + interest)
        else:
            payment_actual = payment

        extra = extras_map.get((payment_date.year, payment_date.month), ZERO)
        if extra > ZERO and extra > balance - scheduled_principal:
            extra = balance - scheduled_principal

        new_balance = _q(balance - scheduled_principal - extra)
        rows.append(
            PeriodRow(
                period=period,
                due_date=payment_date,
                payment=_q(payment_actual),
                principal=_q(scheduled_principal),
                interest=_q(interest),
                extra=_q(extra),
                balance=new_balance,
            )
        )
        total_interest += interest
        total_extra += extra
        balance = new_balance

        payment_date = _add_months(payment_date, 1)
        period += 1

    payoff_date = rows[-1].due_date if rows else None
    total_principal = sum((r.principal for r in rows), ZERO)
    total_paid = sum((r.payment + r.extra for r in rows), ZERO)

    return Schedule(
        rows=tuple(rows),
        payoff_date=payoff_date,
        total_interest=_q(total_interest),
        total_principal=_q(total_principal),
        total_paid=_q(total_paid),
        total_extra=_q(total_extra),
        months_to_payoff=len(rows),
    )


# ----------------------------- drift detection -----------------------------


@dataclass(frozen=True)
class DriftResult:
    severity: str  # "green" | "yellow" | "red"
    delta: Decimal  # logged - predicted (positive = balance higher than expected)
    predicted: Decimal
    logged: Decimal


def detect_drift(predicted: Decimal, logged: Decimal) -> DriftResult:
    """Compare a logged balance to what amortization predicted.

    Thresholds (from the spec):
        green  : within $50 OR 0.5%, whichever is greater
        yellow : within $250 OR 2%, whichever is greater
        red    : everything else
    """

    delta = logged - predicted
    abs_delta = abs(delta)
    pct = (abs_delta / predicted * Decimal(100)) if predicted > 0 else Decimal("0")

    green_dollar = Decimal("50")
    green_pct = Decimal("0.5")
    yellow_dollar = Decimal("250")
    yellow_pct = Decimal("2")

    is_green = abs_delta <= green_dollar or pct <= green_pct
    is_yellow = abs_delta <= yellow_dollar or pct <= yellow_pct

    if is_green:
        severity = "green"
    elif is_yellow:
        severity = "yellow"
    else:
        severity = "red"

    return DriftResult(
        severity=severity, delta=_q(delta), predicted=_q(predicted), logged=_q(logged)
    )


def predict_balance_at(schedule: Schedule, target: date) -> Decimal | None:
    """Return the predicted closing balance for the period whose due_date <= target."""

    last: Decimal | None = None
    for row in schedule.rows:
        if row.due_date <= target:
            last = row.balance
        else:
            break
    return last


__all__ = [
    "DriftResult",
    "ExtraPaymentInput",
    "LoanTerms",
    "PeriodRow",
    "RateChangeInput",
    "Schedule",
    "build_schedule",
    "detect_drift",
    "fixed_payment",
    "predict_balance_at",
]
