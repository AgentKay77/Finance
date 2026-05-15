"""Subscriptions (Phase 6)."""

from __future__ import annotations

import enum
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.scoping import UserOwnedMixin


class BillingCycle(str, enum.Enum):
    MONTHLY = "monthly"
    ANNUAL = "annual"
    QUARTERLY = "quarterly"
    WEEKLY = "weekly"


_MONEY = Numeric(12, 2)


class Subscription(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    amount: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    billing_cycle: Mapped[BillingCycle] = mapped_column(
        Enum(BillingCycle, native_enum=False, length=20), nullable=False
    )
    next_renewal_date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str | None] = mapped_column(String(60))
    notes: Mapped[str | None] = mapped_column(String(500))
