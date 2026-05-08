"""Dashboard / hub home page.

Renders compact summary tiles for each module backed by live data.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from flask import Blueprint, render_template
from flask_login import login_required

from app.extensions import db
from app.models import (
    Asset,
    Bill,
    Loan,
    LoanStatus,
    NetWorthSnapshot,
    SavingsGoal,
    Subscription,
    current_user_query,
)
from app.services.amortization import (
    LoanTerms,
    build_schedule,
    predict_balance_at,
)
from app.services.networth import compute_breakdown

bp = Blueprint("dashboard", __name__)


def _liability_for(loan: Loan) -> Decimal:
    latest = max(loan.balance_logs, key=lambda b: b.as_of_date, default=None)
    if latest is not None:
        return Decimal(latest.balance)
    schedule = build_schedule(
        LoanTerms(
            principal=Decimal(loan.original_principal),
            annual_rate=Decimal(loan.current_rate),
            term_months=loan.original_term_months,
            payment_amount=Decimal(loan.payment_amount),
            first_payment_date=loan.first_payment_date,
        )
    )
    return predict_balance_at(schedule, date.today()) or Decimal(loan.original_principal)


@bp.route("/")
@login_required
def home() -> str:
    today = date.today()
    horizon = today + timedelta(days=30)

    loans = (
        db.session.execute(current_user_query(Loan).where(Loan.status == LoanStatus.ACTIVE))
        .scalars()
        .all()
    )
    assets = db.session.execute(current_user_query(Asset)).scalars().all()

    asset_rows = [(a.name, Decimal(a.current_value)) for a in assets]
    liability_rows = [(loan.name, _liability_for(loan)) for loan in loans]
    breakdown = compute_breakdown(asset_rows, liability_rows, today)

    snapshots = (
        db.session.execute(
            current_user_query(NetWorthSnapshot).order_by(NetWorthSnapshot.snapshot_date)
        )
        .scalars()
        .all()
    )
    last_snapshot = snapshots[-1] if snapshots else None

    bills_due_soon = (
        db.session.execute(
            current_user_query(Bill)
            .where(Bill.next_due_date <= horizon)
            .order_by(Bill.next_due_date)
        )
        .scalars()
        .all()
    )
    goals = (
        db.session.execute(current_user_query(SavingsGoal).order_by(SavingsGoal.target_date))
        .scalars()
        .all()
    )
    subs = (
        db.session.execute(
            current_user_query(Subscription).order_by(Subscription.next_renewal_date)
        )
        .scalars()
        .all()
    )

    return render_template(
        "dashboard/home.html",
        loan_count=len(loans),
        loan_total=breakdown.liabilities_total,
        net_worth=breakdown.net_worth,
        last_snapshot=last_snapshot,
        bills_due_soon=bills_due_soon,
        goal_count=len(goals),
        sub_count=len(subs),
    )


@bp.route("/healthz")
def healthz() -> tuple[str, int]:
    return "ok", 200
