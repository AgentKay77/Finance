"""SQLAlchemy models for the finance hub.

Importing this package registers every model with the shared declarative base
so Alembic autogeneration can see them.
"""

from app.models.asset import Asset, NetWorthSnapshot
from app.models.base import Base, TimestampMixin
from app.models.bill import Bill, BillRecurrence
from app.models.budget import BudgetCategory, BudgetTransaction, TransactionSource
from app.models.goal import SavingsGoal
from app.models.loan import (
    BalanceLog,
    ExtraPayment,
    ExtraPaymentFrequency,
    ExtraPaymentType,
    Loan,
    LoanStatus,
    LoanType,
    RateChange,
    ScheduledPayment,
)
from app.models.scoping import UserOwnedMixin, current_user_id, current_user_query
from app.models.subscription import BillingCycle, Subscription
from app.models.user import User

__all__ = [
    "Asset",
    "BalanceLog",
    "Base",
    "Bill",
    "BillRecurrence",
    "BillingCycle",
    "BudgetCategory",
    "BudgetTransaction",
    "TransactionSource",
    "ExtraPayment",
    "ExtraPaymentFrequency",
    "ExtraPaymentType",
    "Loan",
    "LoanStatus",
    "LoanType",
    "NetWorthSnapshot",
    "RateChange",
    "SavingsGoal",
    "ScheduledPayment",
    "Subscription",
    "TimestampMixin",
    "User",
    "UserOwnedMixin",
    "current_user_id",
    "current_user_query",
]
