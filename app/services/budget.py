"""Budget rollup math.

Computes month-to-date spending per category and the on-pace / off-pace
flag used by the dashboard tile and budget home page. Pure functions —
input is plain (category, transactions) pairs, output is dataclasses.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

ZERO = Decimal("0")


def days_in_month(d: date) -> int:
    return monthrange(d.year, d.month)[1]


@dataclass(frozen=True)
class CategoryRollup:
    category_id: int
    name: str
    color: str
    sort_order: int
    monthly_limit: Decimal
    spent: Decimal
    percent_spent: Decimal  # 0..N (can exceed 100)
    on_pace: bool  # True when percent_spent <= percent_of_month_elapsed


@dataclass(frozen=True)
class MonthSummary:
    year: int
    month: int
    total_spent: Decimal
    total_limit: Decimal
    percent_of_month_elapsed: Decimal  # 0..100
    categories: tuple[CategoryRollup, ...]

    @property
    def categories_over_pace(self) -> int:
        return sum(1 for c in self.categories if not c.on_pace and c.monthly_limit > ZERO)


def rollup_month(
    categories: list[tuple[int, str, str, int, Decimal]],
    transactions: list[tuple[int, Decimal, date]],
    as_of: date,
) -> MonthSummary:
    """Build a MonthSummary for the month containing ``as_of``.

    ``categories``: list of (id, name, color, sort_order, monthly_limit).
    ``transactions``: list of (category_id, amount, date) — caller is
    responsible for filtering to the relevant month.
    """

    total_in_month = days_in_month(as_of)
    pct_elapsed = (Decimal(as_of.day) / Decimal(total_in_month) * Decimal(100)).quantize(
        Decimal("0.01")
    )

    sums: dict[int, Decimal] = {cid: ZERO for cid, *_ in categories}
    for cid, amount, _txn_date in transactions:
        sums[cid] = sums.get(cid, ZERO) + amount

    rollups: list[CategoryRollup] = []
    total_spent = ZERO
    total_limit = ZERO
    for cid, name, color, sort_order, limit in categories:
        spent = sums.get(cid, ZERO)
        pct = (spent / limit * Decimal(100)) if limit > 0 else ZERO
        rollups.append(
            CategoryRollup(
                category_id=cid,
                name=name,
                color=color,
                sort_order=sort_order,
                monthly_limit=limit,
                spent=spent.quantize(Decimal("0.01")),
                percent_spent=pct.quantize(Decimal("0.01")),
                on_pace=pct <= pct_elapsed,
            )
        )
        total_spent += spent
        total_limit += limit

    rollups.sort(key=lambda r: (r.sort_order, r.name))
    return MonthSummary(
        year=as_of.year,
        month=as_of.month,
        total_spent=total_spent.quantize(Decimal("0.01")),
        total_limit=total_limit.quantize(Decimal("0.01")),
        percent_of_month_elapsed=pct_elapsed,
        categories=tuple(rollups),
    )


__all__ = ["CategoryRollup", "MonthSummary", "days_in_month", "rollup_month"]
