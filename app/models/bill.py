"""Bill calendar models (Phase 4)."""

from __future__ import annotations

import enum
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, Enum, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.scoping import UserOwnedMixin


class BillRecurrence(str, enum.Enum):
    MONTHLY = "monthly"
    BIWEEKLY = "biweekly"
    WEEKLY = "weekly"
    ANNUAL = "annual"
    QUARTERLY = "quarterly"
    ONE_TIME = "one_time"


_MONEY = Numeric(12, 2)


class Bill(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "bills"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    amount: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    recurrence: Mapped[BillRecurrence] = mapped_column(
        Enum(BillRecurrence, native_enum=False, length=20), nullable=False
    )
    next_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    autopay: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    category: Mapped[str | None] = mapped_column(String(60))
    notes: Mapped[str | None] = mapped_column(String(500))
