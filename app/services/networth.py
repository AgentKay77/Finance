"""Net worth calculations (Phase 3).

Pulls assets from the assets table and current liabilities from each
loan's most recent BalanceLog entry (or the predicted balance from
amortization if no log exists yet).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.services.amortization import ZERO, _q


@dataclass(frozen=True)
class NetWorthBreakdown:
    as_of: date
    assets_total: Decimal
    liabilities_total: Decimal
    net_worth: Decimal
    by_asset: tuple[tuple[str, Decimal], ...]
    by_liability: tuple[tuple[str, Decimal], ...]


def compute_breakdown(
    asset_rows: Iterable[tuple[str, Decimal]],
    liability_rows: Iterable[tuple[str, Decimal]],
    as_of: date,
) -> NetWorthBreakdown:
    """Sum assets and liabilities into a snapshot.

    Inputs are tuples (label, amount) so the service stays decoupled
    from SQLAlchemy rows.
    """

    assets = [(label, _q(amt)) for label, amt in asset_rows]
    liabilities = [(label, _q(amt)) for label, amt in liability_rows]
    assets_total = sum((a[1] for a in assets), ZERO)
    liabilities_total = sum((liab[1] for liab in liabilities), ZERO)
    return NetWorthBreakdown(
        as_of=as_of,
        assets_total=_q(assets_total),
        liabilities_total=_q(liabilities_total),
        net_worth=_q(assets_total - liabilities_total),
        by_asset=tuple(assets),
        by_liability=tuple(liabilities),
    )


__all__ = ["NetWorthBreakdown", "compute_breakdown"]
