"""Loan tracker models (Phase 2).

The amortization service in :mod:`app.services.amortization` operates on
plain ``Decimal``s and dataclasses derived from these rows; nothing in
that module touches the DB.
"""

from __future__ import annotations

import enum
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.scoping import UserOwnedMixin


class LoanType(str, enum.Enum):
    MORTGAGE = "mortgage"
    AUTO = "auto"
    STUDENT = "student"
    PERSONAL = "personal"
    CREDIT_CARD = "credit_card"
    OTHER = "other"


class LoanStatus(str, enum.Enum):
    ACTIVE = "active"
    PAID_OFF = "paid_off"
    CLOSED = "closed"


class BalanceSource(str, enum.Enum):
    MANUAL = "manual"
    STATEMENT = "statement"
    COMPUTED = "computed"


class ExtraPaymentType(str, enum.Enum):
    ONE_TIME = "one_time"
    RECURRING = "recurring"


class ExtraPaymentFrequency(str, enum.Enum):
    MONTHLY = "monthly"
    BIWEEKLY = "biweekly"
    ANNUAL = "annual"


_MONEY = Numeric(12, 2)
_RATE = Numeric(7, 5)  # APR like 0.06375


class Loan(UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "loans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    lender: Mapped[str | None] = mapped_column(String(120))
    loan_type: Mapped[LoanType] = mapped_column(
        Enum(LoanType, native_enum=False, length=20), nullable=False
    )
    original_principal: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    current_rate: Mapped[Decimal] = mapped_column(_RATE, nullable=False)
    original_term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_amount: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    first_payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_day_of_month: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[LoanStatus] = mapped_column(
        Enum(LoanStatus, native_enum=False, length=20),
        nullable=False,
        default=LoanStatus.ACTIVE,
    )
    notes: Mapped[str | None] = mapped_column(Text)

    # Day count convention for interest accrual. "actual/360" (default) treats
    # every elapsed calendar day as 1/360 of a year. "30/360" is the bond-math
    # convention. Only these two are recognised by the amortization service.
    day_count_convention: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="30/360", default="30/360"
    )

    # Set by the "recalibrate from current balance" action so future schedule
    # builds start from this observed balance instead of original principal.
    recalibration_balance: Mapped[Decimal | None] = mapped_column(_MONEY)
    recalibration_date: Mapped[date | None] = mapped_column(Date)

    balance_logs: Mapped[list[BalanceLog]] = relationship(
        back_populates="loan", cascade="all, delete-orphan"
    )
    scheduled_payments: Mapped[list[ScheduledPayment]] = relationship(
        back_populates="loan", cascade="all, delete-orphan"
    )
    extra_payments: Mapped[list[ExtraPayment]] = relationship(
        back_populates="loan", cascade="all, delete-orphan"
    )
    rate_changes: Mapped[list[RateChange]] = relationship(
        back_populates="loan", cascade="all, delete-orphan"
    )


class BalanceLog(TimestampMixin, Base):
    __tablename__ = "balance_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    loan_id: Mapped[int] = mapped_column(
        ForeignKey("loans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    balance: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    source: Mapped[BalanceSource] = mapped_column(
        Enum(BalanceSource, native_enum=False, length=20),
        nullable=False,
        default=BalanceSource.MANUAL,
    )
    notes: Mapped[str | None] = mapped_column(Text)

    loan: Mapped[Loan] = relationship(back_populates="balance_logs")


class ScheduledPayment(Base):
    __tablename__ = "scheduled_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    loan_id: Mapped[int] = mapped_column(
        ForeignKey("loans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_principal: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    scheduled_interest: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    scheduled_balance: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)

    loan: Mapped[Loan] = relationship(back_populates="scheduled_payments")


class ExtraPayment(TimestampMixin, Base):
    __tablename__ = "extra_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    loan_id: Mapped[int] = mapped_column(
        ForeignKey("loans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    payment_type: Mapped[ExtraPaymentType] = mapped_column(
        Enum(ExtraPaymentType, native_enum=False, length=20), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    frequency: Mapped[ExtraPaymentFrequency | None] = mapped_column(
        Enum(ExtraPaymentFrequency, native_enum=False, length=20)
    )
    notes: Mapped[str | None] = mapped_column(Text)

    loan: Mapped[Loan] = relationship(back_populates="extra_payments")


class RateChange(Base):
    __tablename__ = "rate_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    loan_id: Mapped[int] = mapped_column(
        ForeignKey("loans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    new_rate: Mapped[Decimal] = mapped_column(_RATE, nullable=False)

    loan: Mapped[Loan] = relationship(back_populates="rate_changes")
