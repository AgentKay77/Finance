"""Budget categories + transactions + month dashboard."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import and_, extract, select

from app.blueprints.budget.forms import CategoryForm, TransactionForm
from app.extensions import db
from app.models import (
    BudgetCategory,
    BudgetTransaction,
    TransactionSource,
    current_user_id,
    current_user_query,
)
from app.services.budget import rollup_month

bp = Blueprint("budget", __name__, url_prefix="/budget", template_folder="../../templates/budget")


def _category_tuples(categories):
    return [(c.id, c.name, c.color, c.sort_order, Decimal(c.monthly_limit)) for c in categories]


def _transactions_for_month(user_id: int, year: int, month: int):
    """Fetch transactions for a single user/month as (cat_id, amount, date)."""
    rows = (
        db.session.execute(
            select(BudgetTransaction).where(
                BudgetTransaction.user_id == user_id,
                extract("year", BudgetTransaction.date) == year,
                extract("month", BudgetTransaction.date) == month,
            )
        )
        .scalars()
        .all()
    )
    return [(r.category_id, Decimal(r.amount), r.date) for r in rows]


def _get_category_or_404(category_id: int) -> BudgetCategory:
    cat = db.session.execute(
        current_user_query(BudgetCategory).where(BudgetCategory.id == category_id)
    ).scalar_one_or_none()
    if cat is None:
        abort(404)
    return cat


def _get_transaction_or_404(txn_id: int) -> BudgetTransaction:
    txn = db.session.execute(
        current_user_query(BudgetTransaction).where(BudgetTransaction.id == txn_id)
    ).scalar_one_or_none()
    if txn is None:
        abort(404)
    return txn


@bp.route("/")
@login_required
def home() -> str:
    today = date.today()
    user_id = current_user_id()
    cats = (
        db.session.execute(
            current_user_query(BudgetCategory).order_by(
                BudgetCategory.sort_order, BudgetCategory.name
            )
        )
        .scalars()
        .all()
    )
    summary = rollup_month(
        _category_tuples(cats), _transactions_for_month(user_id, today.year, today.month), today
    )
    return render_template("budget/home.html", summary=summary, today=today, any_cats=bool(cats))


@bp.route("/months/<int:year>-<int:month>")
@login_required
def month_view(year: int, month: int) -> str:
    if month < 1 or month > 12:
        abort(404)
    user_id = current_user_id()
    # Last day of the requested month, so pct-elapsed reads as 100%.
    from calendar import monthrange

    as_of = date(year, month, monthrange(year, month)[1])
    cats = (
        db.session.execute(
            current_user_query(BudgetCategory).order_by(
                BudgetCategory.sort_order, BudgetCategory.name
            )
        )
        .scalars()
        .all()
    )
    summary = rollup_month(
        _category_tuples(cats), _transactions_for_month(user_id, year, month), as_of
    )
    return render_template(
        "budget/month.html", summary=summary, year=year, month=month, today=date.today()
    )


# ---------- Categories ----------


@bp.route("/categories/")
@login_required
def list_categories() -> str:
    cats = (
        db.session.execute(
            current_user_query(BudgetCategory).order_by(
                BudgetCategory.sort_order, BudgetCategory.name
            )
        )
        .scalars()
        .all()
    )
    return render_template("budget/categories.html", categories=cats)


@bp.route("/categories/new", methods=["GET", "POST"])
@login_required
def new_category() -> str:
    form = CategoryForm()
    if form.validate_on_submit():
        cat = BudgetCategory(
            user_id=current_user_id(),
            name=form.name.data.strip(),
            monthly_limit=form.monthly_limit.data,
            color=form.color.data,
            sort_order=form.sort_order.data or 0,
        )
        db.session.add(cat)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("That category name already exists.", "error")
            return render_template("budget/category_edit.html", form=form, category=None)
        flash("Category created.", "success")
        return redirect(url_for("budget.list_categories"))
    return render_template("budget/category_edit.html", form=form, category=None)


@bp.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
@login_required
def edit_category(category_id: int) -> str:
    cat = _get_category_or_404(category_id)
    form = CategoryForm(obj=cat)
    if form.validate_on_submit():
        cat.name = form.name.data.strip()
        cat.monthly_limit = form.monthly_limit.data
        cat.color = form.color.data
        cat.sort_order = form.sort_order.data or 0
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("That category name already exists.", "error")
            return render_template("budget/category_edit.html", form=form, category=cat)
        flash("Category updated.", "success")
        return redirect(url_for("budget.list_categories"))
    return render_template("budget/category_edit.html", form=form, category=cat)


@bp.route("/categories/<int:category_id>/delete", methods=["POST"])
@login_required
def delete_category(category_id: int) -> str:
    cat = _get_category_or_404(category_id)
    # Refuse if transactions reference this category.
    count = db.session.execute(
        select(BudgetTransaction).where(BudgetTransaction.category_id == cat.id)
    ).scalars()
    count_value = sum(1 for _ in count)
    if count_value > 0:
        flash(
            f"Reassign {count_value} transaction(s) before deleting '{cat.name}'.",
            "error",
        )
        return redirect(url_for("budget.list_categories"))
    db.session.delete(cat)
    db.session.commit()
    flash("Category deleted.", "info")
    return redirect(url_for("budget.list_categories"))


# ---------- Transactions ----------


def _category_choices() -> list[tuple[int, str]]:
    cats = (
        db.session.execute(current_user_query(BudgetCategory).order_by(BudgetCategory.name))
        .scalars()
        .all()
    )
    return [(c.id, c.name) for c in cats]


@bp.route("/transactions/", methods=["GET", "POST"])
@login_required
def list_transactions() -> str:
    choices = _category_choices()
    form = TransactionForm()
    form.category_id.choices = choices
    if form.validate_on_submit() and choices:
        txn = BudgetTransaction(
            user_id=current_user_id(),
            category_id=form.category_id.data,
            amount=form.amount.data,
            date=form.txn_date.data,
            note=form.note.data or None,
            source=TransactionSource.MANUAL,
        )
        db.session.add(txn)
        db.session.commit()
        flash("Transaction added.", "success")
        return redirect(url_for("budget.list_transactions"))

    # Filters
    month_filter = request.args.get("month")  # "YYYY-MM"
    category_filter = request.args.get("category", type=int)
    search = (request.args.get("q") or "").strip()

    stmt = current_user_query(BudgetTransaction).order_by(BudgetTransaction.date.desc())
    if month_filter:
        try:
            y, m = month_filter.split("-")
            stmt = stmt.where(
                and_(
                    extract("year", BudgetTransaction.date) == int(y),
                    extract("month", BudgetTransaction.date) == int(m),
                )
            )
        except ValueError:
            pass
    if category_filter:
        stmt = stmt.where(BudgetTransaction.category_id == category_filter)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(BudgetTransaction.note.ilike(like))

    transactions = db.session.execute(stmt).scalars().all()
    cat_map = {cid: name for cid, name in choices}
    return render_template(
        "budget/transactions.html",
        form=form,
        transactions=transactions,
        cat_map=cat_map,
        choices=choices,
        month_filter=month_filter or "",
        category_filter=category_filter or "",
        search=search,
    )


@bp.route("/transactions/<int:txn_id>/edit", methods=["GET", "POST"])
@login_required
def edit_transaction(txn_id: int) -> str:
    txn = _get_transaction_or_404(txn_id)
    form = TransactionForm(
        category_id=txn.category_id,
        amount=txn.amount,
        txn_date=txn.date,
        note=txn.note or "",
    )
    form.category_id.choices = _category_choices()
    if form.validate_on_submit():
        txn.category_id = form.category_id.data
        txn.amount = form.amount.data
        txn.date = form.txn_date.data
        txn.note = form.note.data or None
        db.session.commit()
        flash("Transaction updated.", "success")
        return redirect(url_for("budget.list_transactions"))
    return render_template("budget/transaction_edit.html", form=form, txn=txn)


@bp.route("/transactions/<int:txn_id>/delete", methods=["POST"])
@login_required
def delete_transaction(txn_id: int) -> str:
    txn = _get_transaction_or_404(txn_id)
    db.session.delete(txn)
    db.session.commit()
    flash("Transaction deleted.", "info")
    return redirect(url_for("budget.list_transactions"))
