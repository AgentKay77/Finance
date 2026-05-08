"""Snowball vs avalanche payoff projections (Phase 2).

Operates on plain inputs so the Phase 5 what-if module can call this
without paying SQLAlchemy overhead. Each strategy returns parallel
projections: snowball (smallest balance first), avalanche (highest APR
first), and a "minimum-only" baseline used to compute savings.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.services.amortization import (
    CENT,
    ZERO,
    _add_months,
    _q,
    fixed_payment,
)


@dataclass(frozen=True)
class StrategyLoan:
    """Snapshot of a loan suitable for strategy projections.

    ``current_balance`` lets us project from today rather than from
    origination — the user's loans are usually mid-life when they enter
    them in this app.
    """

    id: int
    name: str
    current_balance: Decimal
    annual_rate: Decimal
    minimum_payment: Decimal
    next_payment_date: date


@dataclass(frozen=True)
class PayoffStep:
    period: int
    on_date: date
    balances: dict[int, Decimal]  # by loan id
    principal_paid: Decimal
    interest_paid: Decimal


@dataclass(frozen=True)
class StrategyResult:
    name: str
    months_to_debt_free: int
    total_interest: Decimal
    total_paid: Decimal
    payoff_order: tuple[tuple[int, date], ...]  # (loan_id, paid-off date)
    monthly_balance_total: tuple[tuple[date, Decimal], ...]
    interest_savings_vs_baseline: Decimal


@dataclass(frozen=True)
class ComparisonResult:
    snowball: StrategyResult
    avalanche: StrategyResult
    baseline: StrategyResult


MAX_MONTHS = 1200


def _project(
    loans: list[StrategyLoan],
    extra_budget: Decimal,
    sort_key,
    *,
    label: str,
) -> StrategyResult:
    state = {
        loan.id: {
            "balance": _q(loan.current_balance),
            "rate": loan.annual_rate,
            "minimum": _q(loan.minimum_payment),
            "name": loan.name,
        }
        for loan in loans
    }
    if not state:
        return StrategyResult(
            name=label,
            months_to_debt_free=0,
            total_interest=ZERO,
            total_paid=ZERO,
            payoff_order=(),
            monthly_balance_total=(),
            interest_savings_vs_baseline=ZERO,
        )

    cursor = min(loan.next_payment_date for loan in loans)
    payoff_order: list[tuple[int, date]] = []
    monthly_total: list[tuple[date, Decimal]] = []
    total_interest = ZERO
    total_paid = ZERO

    for _month in range(1, MAX_MONTHS + 1):
        active_ids = [lid for lid, s in state.items() if s["balance"] > ZERO]
        if not active_ids:
            break

        # Apply each loan's minimum: interest then principal.
        period_interest = ZERO
        period_principal = ZERO
        for lid in active_ids:
            s = state[lid]
            interest = _q(s["balance"] * s["rate"] / Decimal(12))
            payment = min(s["minimum"], _q(s["balance"] + interest))
            principal = _q(payment - interest)
            if principal < ZERO:
                principal = ZERO
            s["balance"] = _q(s["balance"] - principal)
            period_interest += interest
            period_principal += principal
            total_paid += payment

        # Allocate extra + freed-up minimums of paid-off loans to the
        # target chosen by sort_key.
        active_ids = [lid for lid, s in state.items() if s["balance"] > ZERO]
        freed = sum(
            (state[lid]["minimum"] for lid in state if state[lid]["balance"] <= ZERO),
            ZERO,
        )
        avalanche_pool = extra_budget + freed
        if active_ids and avalanche_pool > ZERO:
            target_id = sorted(active_ids, key=lambda lid: sort_key(state[lid]))[0]
            s = state[target_id]
            allocate = min(avalanche_pool, s["balance"])
            s["balance"] = _q(s["balance"] - allocate)
            period_principal += allocate
            total_paid += allocate

        total_interest += period_interest

        # Record any payoffs that just happened.
        for lid in list(state.keys()):
            if state[lid]["balance"] <= ZERO and lid not in {p[0] for p in payoff_order}:
                payoff_order.append((lid, cursor))

        balance_total = sum((s["balance"] for s in state.values()), ZERO)
        monthly_total.append((cursor, _q(balance_total)))

        if balance_total <= CENT:
            break

        cursor = _add_months(cursor, 1)

    return StrategyResult(
        name=label,
        months_to_debt_free=len(monthly_total),
        total_interest=_q(total_interest),
        total_paid=_q(total_paid),
        payoff_order=tuple(payoff_order),
        monthly_balance_total=tuple(monthly_total),
        interest_savings_vs_baseline=ZERO,  # populated by caller
    )


def compare_strategies(
    loans: Iterable[StrategyLoan],
    monthly_extra_budget: Decimal,
) -> ComparisonResult:
    loan_list = list(loans)

    snowball_key = lambda s: s["balance"]  # noqa: E731
    avalanche_key = lambda s: -s["rate"]  # noqa: E731
    none_extra = Decimal("0")

    baseline = _project(loan_list, none_extra, snowball_key, label="Minimum only")
    snowball = _project(loan_list, monthly_extra_budget, snowball_key, label="Snowball")
    avalanche = _project(loan_list, monthly_extra_budget, avalanche_key, label="Avalanche")

    def _with_savings(r: StrategyResult) -> StrategyResult:
        return StrategyResult(
            name=r.name,
            months_to_debt_free=r.months_to_debt_free,
            total_interest=r.total_interest,
            total_paid=r.total_paid,
            payoff_order=r.payoff_order,
            monthly_balance_total=r.monthly_balance_total,
            interest_savings_vs_baseline=_q(baseline.total_interest - r.total_interest),
        )

    return ComparisonResult(
        snowball=_with_savings(snowball),
        avalanche=_with_savings(avalanche),
        baseline=baseline,
    )


def loan_to_strategy(loan_row, current_balance: Decimal) -> StrategyLoan:
    """Lift a SQLAlchemy Loan row into a strategy input."""
    return StrategyLoan(
        id=loan_row.id,
        name=loan_row.name,
        current_balance=current_balance,
        annual_rate=loan_row.current_rate,
        minimum_payment=loan_row.payment_amount,
        next_payment_date=loan_row.first_payment_date,
    )


__all__ = [
    "ComparisonResult",
    "PayoffStep",
    "StrategyLoan",
    "StrategyResult",
    "compare_strategies",
    "fixed_payment",
    "loan_to_strategy",
]
