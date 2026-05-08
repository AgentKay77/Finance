"""Tests for the net worth service."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.services.networth import compute_breakdown


def test_breakdown_sums_assets_and_liabilities() -> None:
    breakdown = compute_breakdown(
        asset_rows=[("Checking", Decimal("5000")), ("Brokerage", Decimal("42000.50"))],
        liability_rows=[("Mortgage", Decimal("280000")), ("Auto", Decimal("9500"))],
        as_of=date(2026, 5, 1),
    )
    assert breakdown.assets_total == Decimal("47000.50")
    assert breakdown.liabilities_total == Decimal("289500.00")
    assert breakdown.net_worth == Decimal("-242499.50")


def test_breakdown_handles_no_inputs() -> None:
    breakdown = compute_breakdown([], [], date(2026, 5, 1))
    assert breakdown.assets_total == Decimal("0")
    assert breakdown.liabilities_total == Decimal("0")
    assert breakdown.net_worth == Decimal("0")
