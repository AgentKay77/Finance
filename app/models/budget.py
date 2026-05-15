"""Budget categories and transactions.

Two tables — categories define a monthly spending envelope; transactions
record individual line items against a category. Auto-created transactions
(e.g. from a bill being marked paid) carry ``source='auto'`` so they can
be filtered or reconciled later.
"""

from __future__ import annotations

import enum
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.scoping import UserOwnedMixin

_MONEY = Numeric(12, 2)


class TransactionSource(str, enum.Enum):
    MANUAL = "manual"
    AUTO_BILL = "auto_bill"  # created when a bill is marked paid


class BudgetCategory(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "budget_categories"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_budget_categories_user_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    monthly_limit: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    color: Mapped[str] = mapped_column(String(9), nullable=False, default="#38bdf8")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    transactions: Mapped[list[BudgetTransaction]] = relationship(back_populates="category")


class BudgetTransaction(UserOwnedMixin, Base):
    __tablename__ = "budget_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("budget_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(String(200))
    source: Mapped[TransactionSource] = mapped_column(
        Enum(TransactionSource, native_enum=False, length=20),
        nullable=False,
        default=TransactionSource.MANUAL,
    )

    category: Mapped[BudgetCategory] = relationship(back_populates="transactions")
