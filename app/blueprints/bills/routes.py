"""Bill calendar routes."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.blueprints.bills.forms import BillForm
from app.extensions import db
from app.models import (
    Bill,
    BudgetCategory,
    BudgetTransaction,
    Loan,
    TransactionSource,
    current_user_id,
    current_user_query,
)
from app.models.bill import BillRecurrence
from app.services.amortization import _add_months
from app.services.recurrence import advance_due_date, next_occurrences


def _budget_category_choices() -> list[tuple[str, str]]:
    """Choices for the bill's default-budget-category dropdown.

    Blank option means 'don't auto-create a transaction'.
    """
    cats = (
        db.session.execute(current_user_query(BudgetCategory).order_by(BudgetCategory.name))
        .scalars()
        .all()
    )
    return [("", "— none —")] + [(str(c.id), c.name) for c in cats]


bp = Blueprint("bills", __name__, url_prefix="/bills", template_folder="../../templates/bills")


@bp.route("/")
@login_required
def list_bills() -> str:
    bills = (
        db.session.execute(current_user_query(Bill).order_by(Bill.next_due_date)).scalars().all()
    )
    today = date.today()
    return render_template("bills/list.html", bills=bills, today=today)


@bp.route("/cashflow")
@login_required
def cashflow() -> str:
    """Project the next 6 months of bills + scheduled loan payments."""
    bills = db.session.execute(current_user_query(Bill)).scalars().all()
    loans = db.session.execute(current_user_query(Loan)).scalars().all()

    today = date.today()
    horizon = _add_months(today, 6)

    by_month: dict[tuple[int, int], list[tuple[date, str, Decimal, str]]] = defaultdict(list)

    for bill in bills:
        for due in next_occurrences(bill.next_due_date, bill.recurrence.value, horizon):
            if bill.end_date and due > bill.end_date:
                continue
            by_month[(due.year, due.month)].append((due, bill.name, Decimal(bill.amount), "bill"))

    for loan in loans:
        cursor = max(
            loan.first_payment_date,
            today.replace(day=loan.payment_day_of_month if loan.payment_day_of_month <= 28 else 1),
        )
        for _ in range(8):
            if cursor > horizon:
                break
            by_month[(cursor.year, cursor.month)].append(
                (cursor, loan.name, Decimal(loan.payment_amount), "loan")
            )
            cursor = _add_months(cursor, 1)

    months = []
    for key in sorted(by_month.keys()):
        items = sorted(by_month[key])
        total = sum((amt for _, _, amt, _ in items), Decimal("0"))
        months.append({"year": key[0], "month": key[1], "items": items, "total": total})

    return render_template("bills/cashflow.html", months=months)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_bill() -> str:
    form = BillForm()
    form.default_budget_category_id.choices = _budget_category_choices()
    if form.validate_on_submit():
        bill = Bill(
            user_id=current_user_id(),
            name=form.name.data,
            amount=form.amount.data,
            recurrence=BillRecurrence(form.recurrence.data),
            next_due_date=form.next_due_date.data,
            end_date=form.end_date.data,
            autopay=form.autopay.data,
            category=form.category.data or None,
            default_budget_category_id=form.default_budget_category_id.data or None,
            notes=form.notes.data or None,
        )
        db.session.add(bill)
        db.session.commit()
        flash("Bill added.", "success")
        return redirect(url_for("bills.list_bills"))
    return render_template("bills/edit.html", form=form, bill=None)


@bp.route("/<int:bill_id>/edit", methods=["GET", "POST"])
@login_required
def edit_bill(bill_id: int) -> str:
    bill = db.session.execute(
        current_user_query(Bill).where(Bill.id == bill_id)
    ).scalar_one_or_none()
    if bill is None:
        abort(404)
    form = BillForm(obj=bill)
    form.default_budget_category_id.choices = _budget_category_choices()
    if request.method == "GET":
        form.default_budget_category_id.data = bill.default_budget_category_id or None
    if form.validate_on_submit():
        bill.name = form.name.data
        bill.amount = form.amount.data
        bill.recurrence = BillRecurrence(form.recurrence.data)
        bill.next_due_date = form.next_due_date.data
        bill.end_date = form.end_date.data
        bill.autopay = form.autopay.data
        bill.category = form.category.data or None
        bill.default_budget_category_id = form.default_budget_category_id.data or None
        bill.notes = form.notes.data or None
        db.session.commit()
        flash("Bill updated.", "success")
        return redirect(url_for("bills.list_bills"))
    return render_template("bills/edit.html", form=form, bill=bill)


@bp.route("/<int:bill_id>/paid", methods=["POST"])
@login_required
def mark_paid(bill_id: int) -> str:
    bill = db.session.execute(
        current_user_query(Bill).where(Bill.id == bill_id)
    ).scalar_one_or_none()
    if bill is None:
        abort(404)
    paid_date = bill.next_due_date
    bill.next_due_date = advance_due_date(bill.next_due_date, bill.recurrence.value)

    # Auto-create a budget transaction if the bill is wired to a category.
    if bill.default_budget_category_id is not None:
        # Confirm the category still belongs to this user (FK has
        # ON DELETE SET NULL so this could be stale).
        cat = db.session.execute(
            current_user_query(BudgetCategory).where(
                BudgetCategory.id == bill.default_budget_category_id
            )
        ).scalar_one_or_none()
        if cat is not None:
            db.session.add(
                BudgetTransaction(
                    user_id=current_user_id(),
                    category_id=cat.id,
                    amount=bill.amount,
                    date=paid_date,
                    note=bill.name,
                    source=TransactionSource.AUTO_BILL,
                )
            )
    db.session.commit()
    flash(f"Marked '{bill.name}' paid; next due {bill.next_due_date}.", "success")
    return redirect(url_for("bills.list_bills"))


@bp.route("/<int:bill_id>/delete", methods=["POST"])
@login_required
def delete_bill(bill_id: int) -> str:
    bill = db.session.execute(
        current_user_query(Bill).where(Bill.id == bill_id)
    ).scalar_one_or_none()
    if bill is None:
        abort(404)
    db.session.delete(bill)
    db.session.commit()
    flash("Bill deleted.", "info")
    return redirect(url_for("bills.list_bills"))
