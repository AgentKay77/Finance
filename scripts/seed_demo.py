"""Seed a demo user with realistic loans, assets, bills, goals, and subs.

Usage (from project root):
    python -m scripts.seed_demo
"""

from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app import create_app
from app.extensions import db
from app.models import (
    Asset,
    BalanceLog,
    Bill,
    BillingCycle,
    BillRecurrence,
    BudgetCategory,
    BudgetTransaction,
    ExtraPayment,
    ExtraPaymentFrequency,
    ExtraPaymentType,
    Loan,
    LoanStatus,
    LoanType,
    SavingsGoal,
    Subscription,
    TransactionSource,
    User,
)
from app.models.asset import AssetType
from app.services.amortization import fixed_payment

DEMO_EMAIL = "demo@finance.local"
DEMO_PASSWORD = "demo-password-123"


def main() -> int:
    app = create_app()
    with app.app_context():
        existing = db.session.execute(
            select(User).where(User.email == DEMO_EMAIL)
        ).scalar_one_or_none()
        if existing is not None:
            print(f"Demo user already exists: {DEMO_EMAIL}")
            return 0

        user = User(email=DEMO_EMAIL, display_name="Demo")
        user.set_password(DEMO_PASSWORD)
        db.session.add(user)
        db.session.flush()

        # --- Loans ---
        mortgage_principal = Decimal("325000")
        mortgage_rate = Decimal("0.06250")
        mortgage = Loan(
            user_id=user.id,
            name="Home mortgage",
            lender="Big Bank",
            loan_type=LoanType.MORTGAGE,
            original_principal=mortgage_principal,
            current_rate=mortgage_rate,
            original_term_months=360,
            payment_amount=fixed_payment(mortgage_principal, mortgage_rate, 360),
            first_payment_date=date(2024, 3, 1),
            payment_day_of_month=1,
            status=LoanStatus.ACTIVE,
        )
        auto_principal = Decimal("28500")
        auto_rate = Decimal("0.0599")
        auto = Loan(
            user_id=user.id,
            name="Auto",
            lender="Credit Union",
            loan_type=LoanType.AUTO,
            original_principal=auto_principal,
            current_rate=auto_rate,
            original_term_months=60,
            payment_amount=fixed_payment(auto_principal, auto_rate, 60),
            first_payment_date=date(2025, 1, 15),
            payment_day_of_month=15,
            status=LoanStatus.ACTIVE,
        )
        cc_principal = Decimal("4200")
        cc_rate = Decimal("0.2399")
        cc = Loan(
            user_id=user.id,
            name="Credit card",
            lender="Card Co",
            loan_type=LoanType.CREDIT_CARD,
            original_principal=cc_principal,
            current_rate=cc_rate,
            original_term_months=36,
            payment_amount=Decimal("180.00"),
            first_payment_date=date(2026, 1, 5),
            payment_day_of_month=5,
            status=LoanStatus.ACTIVE,
        )
        db.session.add_all([mortgage, auto, cc])
        db.session.flush()

        db.session.add_all(
            [
                BalanceLog(
                    loan_id=mortgage.id, as_of_date=date(2026, 4, 1), balance=Decimal("313500")
                ),
                BalanceLog(loan_id=auto.id, as_of_date=date(2026, 4, 1), balance=Decimal("21800")),
                BalanceLog(loan_id=cc.id, as_of_date=date(2026, 4, 1), balance=Decimal("3950")),
                ExtraPayment(
                    loan_id=mortgage.id,
                    payment_type=ExtraPaymentType.RECURRING,
                    amount=Decimal("100"),
                    start_date=date(2024, 3, 1),
                    frequency=ExtraPaymentFrequency.MONTHLY,
                ),
            ]
        )

        # --- Assets ---
        db.session.add_all(
            [
                Asset(
                    user_id=user.id,
                    name="Checking",
                    asset_type=AssetType.CASH,
                    current_value=Decimal("8500"),
                    as_of_date=date(2026, 5, 1),
                ),
                Asset(
                    user_id=user.id,
                    name="Brokerage",
                    asset_type=AssetType.INVESTMENT,
                    current_value=Decimal("142000"),
                    as_of_date=date(2026, 5, 1),
                ),
                Asset(
                    user_id=user.id,
                    name="Home (Zillow est)",
                    asset_type=AssetType.REAL_ESTATE,
                    current_value=Decimal("485000"),
                    as_of_date=date(2026, 5, 1),
                ),
            ]
        )

        # --- Bills ---
        db.session.add_all(
            [
                Bill(
                    user_id=user.id,
                    name="Electric",
                    amount=Decimal("145"),
                    recurrence=BillRecurrence.MONTHLY,
                    next_due_date=date(2026, 5, 18),
                    autopay=True,
                    category="Utilities",
                ),
                Bill(
                    user_id=user.id,
                    name="Internet",
                    amount=Decimal("89.99"),
                    recurrence=BillRecurrence.MONTHLY,
                    next_due_date=date(2026, 5, 22),
                    autopay=True,
                    category="Utilities",
                ),
                Bill(
                    user_id=user.id,
                    name="HOA",
                    amount=Decimal("250"),
                    recurrence=BillRecurrence.QUARTERLY,
                    next_due_date=date(2026, 7, 1),
                    category="Housing",
                ),
                Bill(
                    user_id=user.id,
                    name="Auto insurance",
                    amount=Decimal("780"),
                    recurrence=BillRecurrence.ANNUAL,
                    next_due_date=date(2026, 9, 1),
                    category="Insurance",
                ),
            ]
        )

        # --- Goals ---
        db.session.add_all(
            [
                SavingsGoal(
                    user_id=user.id,
                    name="Emergency fund",
                    target_amount=Decimal("25000"),
                    current_amount=Decimal("12000"),
                    target_date=date(2026, 12, 31),
                ),
                SavingsGoal(
                    user_id=user.id,
                    name="Roof fund",
                    target_amount=Decimal("18000"),
                    current_amount=Decimal("3500"),
                    target_date=date(2028, 6, 1),
                ),
            ]
        )

        # --- Subscriptions ---
        db.session.add_all(
            [
                Subscription(
                    user_id=user.id,
                    name="Streaming bundle",
                    amount=Decimal("19.99"),
                    billing_cycle=BillingCycle.MONTHLY,
                    next_renewal_date=date(2026, 5, 25),
                    category="Entertainment",
                ),
                Subscription(
                    user_id=user.id,
                    name="Cloud storage",
                    amount=Decimal("99"),
                    billing_cycle=BillingCycle.ANNUAL,
                    next_renewal_date=date(2026, 11, 4),
                    category="Tools",
                ),
            ]
        )

        # --- Budget categories + sample transactions ---
        today = date.today()
        first_of_month = today.replace(day=1)
        groceries = BudgetCategory(
            user_id=user.id,
            name="Groceries",
            monthly_limit=Decimal("600"),
            color="#38bdf8",
            sort_order=0,
        )
        dining = BudgetCategory(
            user_id=user.id,
            name="Dining Out",
            monthly_limit=Decimal("250"),
            color="#facc15",
            sort_order=1,
        )
        gas = BudgetCategory(
            user_id=user.id,
            name="Gas",
            monthly_limit=Decimal("180"),
            color="#4ade80",
            sort_order=2,
        )
        subs_misc = BudgetCategory(
            user_id=user.id,
            name="Subscriptions Misc",
            monthly_limit=Decimal("60"),
            color="#a78bfa",
            sort_order=3,
        )
        home_maint = BudgetCategory(
            user_id=user.id,
            name="Home Maintenance",
            monthly_limit=Decimal("200"),
            color="#fb923c",
            sort_order=4,
        )
        db.session.add_all([groceries, dining, gas, subs_misc, home_maint])
        db.session.flush()

        def _txn(cat: BudgetCategory, amount: str, day_offset: int, note: str | None = None):
            return BudgetTransaction(
                user_id=user.id,
                category_id=cat.id,
                amount=Decimal(amount),
                date=first_of_month.replace(day=min(28, max(1, day_offset))),
                note=note,
                source=TransactionSource.MANUAL,
            )

        db.session.add_all(
            [
                _txn(groceries, "94.27", 3, "Costco run"),
                _txn(groceries, "62.10", 5, "Trader Joe's"),
                _txn(groceries, "138.55", 10, "Costco bulk"),
                _txn(groceries, "44.80", 14, "Local market"),
                _txn(dining, "62.40", 4, "Sushi"),
                _txn(dining, "28.00", 8, "Pizza night"),
                _txn(dining, "104.55", 12, "Anniversary dinner"),
                _txn(gas, "48.10", 2, "Shell"),
                _txn(gas, "52.00", 11, "Costco gas"),
                _txn(subs_misc, "9.99", 1, "Newsletter"),
                _txn(subs_misc, "19.99", 6, "Streaming bonus"),
                _txn(home_maint, "85.00", 9, "HVAC filter"),
                _txn(home_maint, "42.50", 13, "Light bulbs"),
            ]
        )

        db.session.commit()
        print(f"Seeded demo user {DEMO_EMAIL} / {DEMO_PASSWORD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
