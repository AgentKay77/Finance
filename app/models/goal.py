"""Savings goals (Phase 6)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.scoping import UserOwnedMixin

_MONEY = Numeric(12, 2)


class SavingsGoal(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "savings_goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    target_amount: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    current_amount: Mapped[Decimal] = mapped_column(_MONEY, nullable=False, default=Decimal("0"))
    target_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(String(500))
