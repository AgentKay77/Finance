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
    ExtraPayment,
    ExtraPaymentFrequency,
    ExtraPaymentType,
    Loan,
    LoanStatus,
    LoanType,
    SavingsGoal,
    Subscription,
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

        db.session.commit()
        print(f"Seeded demo user {DEMO_EMAIL} / {DEMO_PASSWORD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
