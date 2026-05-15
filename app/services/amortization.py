"""Pure-function amortization service.

Given a loan's terms, its extra payments, and any rate changes, build the
full month-by-month payoff schedule. The module is intentionally
side-effect-free: no DB access, no Flask context, no logging of monetary
values. The Phase 5 what-if scenario tool calls this in a tight loop, so
we keep the hot path allocation-light.

Money is :class:`decimal.Decimal` throughout. Half-up rounding to cents
is applied at every period boundary so accumulated drift is bounded.

Internal algorithm (day-level event stream, rewritten 2026-05-15):

The previous implementation bucketed payments by calendar month, which
applied minimum payments and extras as if they posted on the same day.
That produced silent drift when an extra payment fell mid-month — the
borrower's extra principal didn't avoid the next ~14 days of interest.

The current implementation flattens every event (minimum payment, extra
payment, scheduled rate change) into a single list sorted by date.
Between consecutive events we accrue interest as
``balance × annual_rate / 360 × days_between``, then apply the event.
The day-count convention is set per loan; supported values are
``actual/360`` (default, every elapsed calendar day) and ``30/360``
(bond-math convention). PeriodRows are emitted at each minimum-payment
event and capture all interest, principal, and extras applied since
the prior minimum payment.

Standard fixed-rate amortization formula (still used to compute the
target payment when a loan is initialised or re-amortised after a rate
change)::

    M = P * (r(1+r)^n) / ((1+r)^n - 1)
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
ZERO = Decimal("0")
MAX_PERIODS = 1200  # 100 years — guard against runaway loops on bad input.
DEFAULT_DAY_BASIS = "30/360"


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
    day_count_convention: str = DEFAULT_DAY_BASIS


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
    """Return the standard amortizing payment for a fixed-rate loan."""

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


def _days_between(d1: date, d2: date, convention: str) -> int:
    """Day count under the configured convention."""
    if convention == "30/360":
        y1, m1, day1 = d1.year, d1.month, d1.day
        y2, m2, day2 = d2.year, d2.month, d2.day
        if day1 == 31:
            day1 = 30
        if day2 == 31 and day1 == 30:
            day2 = 30
        return (y2 - y1) * 360 + (m2 - m1) * 30 + (day2 - day1)
    if convention != "actual/360":
        raise ValueError(f"Unsupported day count convention: {convention!r}")
    return (d2 - d1).days


def _accrue(balance: Decimal, rate: Decimal, days: int) -> Decimal:
    """Interest accrued over ``days`` at ``rate`` APR, 360-day year basis."""
    if days <= 0 or balance <= ZERO or rate <= ZERO:
        return ZERO
    return balance * rate * Decimal(days) / Decimal(360)


def _expand_extra_payments(
    extras: Iterable[ExtraPaymentInput], horizon_end: date
) -> list[tuple[date, Decimal]]:
    """Flatten extras into a list of (date, amount) events."""

    out: list[tuple[date, Decimal]] = []
    for ep in extras:
        if ep.payment_type == "one_time":
            out.append((ep.start_date, ep.amount))
            continue
        if ep.payment_type != "recurring":
            raise ValueError(f"Unknown extra payment_type: {ep.payment_type!r}")
        end = ep.end_date or horizon_end
        cursor = ep.start_date
        for _ in range(MAX_PERIODS * 2):
            if cursor > end:
                break
            out.append((cursor, ep.amount))
            if ep.frequency == "monthly":
                cursor = _add_months(cursor, 1)
            elif ep.frequency == "biweekly":
                cursor = cursor + timedelta(days=14)
            elif ep.frequency == "annual":
                cursor = _add_months(cursor, 12)
            else:
                raise ValueError(f"Unknown frequency: {ep.frequency!r}")
    return out


def build_schedule(
    terms: LoanTerms,
    extras: Iterable[ExtraPaymentInput] = (),
    rate_changes: Iterable[RateChangeInput] = (),
    *,
    starting_balance: Decimal | None = None,
    starting_date: date | None = None,
    starting_period: int = 1,
) -> Schedule:
    """Build the full amortization schedule using a day-level event stream."""

    convention = terms.day_count_convention or DEFAULT_DAY_BASIS

    balance = _q(starting_balance if starting_balance is not None else terms.principal)
    anchor_date = starting_date or terms.first_payment_date
    # Interest starts accruing from one period before the first payment.
    # In real loans this matches the disbursement-to-first-payment gap.
    accrual_origin = _add_months(anchor_date, -1)
    current_rate = terms.annual_rate
    live_minimum = terms.payment_amount

    horizon = _add_months(anchor_date, terms.term_months + 60)

    # --- Build event stream ---
    # (date, kind, payload)  kind: "min" | "extra" | "rate"
    events: list[tuple[date, str, Decimal | None]] = []

    for i in range(terms.term_months + 60):
        d = _add_months(anchor_date, i)
        if d >= anchor_date:
            events.append((d, "min", None))

    for d, amt in _expand_extra_payments(extras, horizon):
        if d >= anchor_date:
            events.append((d, "extra", amt))

    sorted_changes = sorted(rate_changes, key=lambda r: r.effective_date)
    for rc in sorted_changes:
        if rc.effective_date >= anchor_date:
            events.append((rc.effective_date, "rate", rc.new_rate))

    # On same date: rate changes apply first (so a same-day payment uses
    # the new rate for any subsequent interest), then extras (apply to
    # principal before the next interest cycle), then the minimum.
    priority = {"rate": 0, "extra": 1, "min": 2}
    events.sort(key=lambda e: (e[0], priority[e[1]]))

    rows: list[PeriodRow] = []
    total_interest_all = ZERO
    total_extra_all = ZERO

    last_event_date = accrual_origin
    period_interest = ZERO
    period_principal = ZERO
    period_extra = ZERO
    period_payment = ZERO
    period_number = starting_period

    for event_date, kind, payload in events:
        if balance <= ZERO:
            break

        days = _days_between(last_event_date, event_date, convention)
        interest_accrued = _accrue(balance, current_rate, days)
        balance = balance + interest_accrued
        period_interest += interest_accrued

        if kind == "rate":
            current_rate = payload  # type: ignore[assignment]
            remaining_term = max(1, terms.term_months - (period_number - starting_period))
            live_minimum = fixed_payment(_q(balance), current_rate, remaining_term)
        elif kind == "extra":
            extra_to_apply = min(payload, balance)  # type: ignore[arg-type]
            balance = balance - extra_to_apply
            period_extra += extra_to_apply
            total_extra_all += extra_to_apply
        elif kind == "min":
            # Balance already includes interest accrued this period. The
            # minimum payment covers as much of that balance as it can.
            payment = min(live_minimum, _q(balance))
            interest_paid_now = min(payment, period_interest)
            principal_portion = payment - interest_paid_now
            balance = balance - payment
            period_principal += principal_portion
            period_payment += payment
            total_interest_all += period_interest

            rows.append(
                PeriodRow(
                    period=period_number,
                    due_date=event_date,
                    payment=_q(period_payment),
                    principal=_q(period_principal),
                    interest=_q(period_interest),
                    extra=_q(period_extra),
                    balance=_q(balance),
                )
            )

            period_number += 1
            period_interest = ZERO
            period_principal = ZERO
            period_extra = ZERO
            period_payment = ZERO

            if _q(balance) <= CENT:
                # Loan is paid off (or within a cent). Stop here rather
                # than emit zero-value rows for the remaining term.
                balance = ZERO
                break

            if period_number - starting_period > MAX_PERIODS:
                break

        last_event_date = event_date

    payoff_date = rows[-1].due_date if rows else None
    total_principal_all = sum((r.principal for r in rows), ZERO)
    total_paid_all = sum((r.payment + r.extra for r in rows), ZERO)

    return Schedule(
        rows=tuple(rows),
        payoff_date=payoff_date,
        total_interest=_q(total_interest_all),
        total_principal=_q(total_principal_all),
        total_paid=_q(total_paid_all),
        total_extra=_q(total_extra_all),
        months_to_payoff=len(rows),
    )


# ----------------------------- drift detection -----------------------------


@dataclass(frozen=True)
class DriftResult:
    severity: str  # "green" | "yellow" | "red"
    delta: Decimal
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

    is_green = abs_delta <= Decimal("50") or pct <= Decimal("0.5")
    is_yellow = abs_delta <= Decimal("250") or pct <= Decimal("2")

    if is_green:
        severity = "green"
    elif is_yellow:
        severity = "yellow"
    else:
        severity = "red"

    return DriftResult(
        severity=severity, delta=_q(delta), predicted=_q(predicted), logged=_q(logged)
    )


def drift_band_dollars(predicted: Decimal) -> tuple[Decimal, Decimal]:
    """Return (yellow_band, red_band) dollar widths around ``predicted``.

    Mirrors the rules in :func:`detect_drift` — picks the greater of the
    dollar and percent thresholds. Used by the loan detail chart.
    """
    yellow = max(Decimal("50"), (predicted * Decimal("0.005")).quantize(CENT))
    red = max(Decimal("250"), (predicted * Decimal("0.02")).quantize(CENT))
    return _q(yellow), _q(red)


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
    "DEFAULT_DAY_BASIS",
    "DriftResult",
    "ExtraPaymentInput",
    "LoanTerms",
    "PeriodRow",
    "RateChangeInput",
    "Schedule",
    "build_schedule",
    "detect_drift",
    "drift_band_dollars",
    "fixed_payment",
    "predict_balance_at",
]
