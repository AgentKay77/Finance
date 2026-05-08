"""Loan tracker routes."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.blueprints.loans.forms import (
    BalanceLogForm,
    ExtraPaymentForm,
    LoanForm,
    StrategyForm,
)
from app.extensions import db
from app.models import (
    BalanceLog,
    ExtraPayment,
    ExtraPaymentFrequency,
    ExtraPaymentType,
    Loan,
    LoanStatus,
    LoanType,
    current_user_query,
)
from app.services.amortization import (
    ExtraPaymentInput,
    LoanTerms,
    RateChangeInput,
    build_schedule,
    detect_drift,
    predict_balance_at,
)
from app.services.payoff_strategies import StrategyLoan, compare_strategies

bp = Blueprint("loans", __name__, url_prefix="/loans", template_folder="../../templates/loans")


def _get_loan_or_404(loan_id: int) -> Loan:
    loan = db.session.execute(
        current_user_query(Loan).where(Loan.id == loan_id)
    ).scalar_one_or_none()
    if loan is None:
        abort(404)
    return loan


def _to_terms(loan: Loan, starting_balance: Decimal | None = None) -> LoanTerms:
    return LoanTerms(
        principal=Decimal(loan.original_principal),
        annual_rate=Decimal(loan.current_rate),
        term_months=loan.original_term_months,
        payment_amount=Decimal(loan.payment_amount),
        first_payment_date=loan.first_payment_date,
    )


def _extras_for(loan: Loan) -> list[ExtraPaymentInput]:
    return [
        ExtraPaymentInput(
            payment_type=ep.payment_type.value,
            amount=Decimal(ep.amount),
            start_date=ep.start_date,
            end_date=ep.end_date,
            frequency=ep.frequency.value if ep.frequency else None,
        )
        for ep in loan.extra_payments
    ]


def _rate_changes_for(loan: Loan) -> list[RateChangeInput]:
    return [
        RateChangeInput(effective_date=rc.effective_date, new_rate=Decimal(rc.new_rate))
        for rc in loan.rate_changes
    ]


def _current_balance(loan: Loan) -> tuple[Decimal, str]:
    """Return (balance, severity-or-source) for the most recent state."""
    schedule = build_schedule(_to_terms(loan), _extras_for(loan), _rate_changes_for(loan))
    latest_log = max(loan.balance_logs, key=lambda b: b.as_of_date, default=None)
    if latest_log is None:
        predicted_today = predict_balance_at(schedule, date.today())
        if predicted_today is None:
            return Decimal(loan.original_principal), "predicted"
        return predicted_today, "predicted"
    predicted = predict_balance_at(schedule, latest_log.as_of_date) or Decimal(
        loan.original_principal
    )
    drift = detect_drift(predicted, Decimal(latest_log.balance))
    return Decimal(latest_log.balance), drift.severity


@bp.route("/")
@login_required
def list_loans() -> str:
    rows = db.session.execute(current_user_query(Loan).order_by(Loan.name)).scalars().all()
    cards = []
    for loan in rows:
        balance, severity = _current_balance(loan)
        cards.append(
            {
                "loan": loan,
                "current_balance": balance,
                "severity": severity,
                "balance_history": sorted(
                    [(b.as_of_date, Decimal(b.balance)) for b in loan.balance_logs]
                ),
            }
        )
    return render_template("loans/list.html", cards=cards)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_loan() -> str:
    form = LoanForm()
    if form.validate_on_submit():
        loan = Loan(
            user_id=int(__import__("flask_login").current_user.id),
            name=form.name.data,
            lender=form.lender.data or None,
            loan_type=LoanType(form.loan_type.data),
            original_principal=form.original_principal.data,
            current_rate=form.current_rate.data,
            original_term_months=form.original_term_months.data,
            payment_amount=form.payment_amount.data,
            first_payment_date=form.first_payment_date.data,
            payment_day_of_month=form.payment_day_of_month.data,
            status=LoanStatus(form.status.data),
            notes=form.notes.data or None,
        )
        db.session.add(loan)
        db.session.commit()
        flash("Loan created.", "success")
        return redirect(url_for("loans.detail", loan_id=loan.id))
    return render_template("loans/edit.html", form=form, loan=None)


@bp.route("/<int:loan_id>")
@login_required
def detail(loan_id: int) -> str:
    loan = _get_loan_or_404(loan_id)
    schedule = build_schedule(_to_terms(loan), _extras_for(loan), _rate_changes_for(loan))
    page = max(1, int(request.args.get("page", 1)))
    per_page = 60
    total_rows = len(schedule.rows)
    rows = schedule.rows[(page - 1) * per_page : page * per_page]
    pages = (total_rows + per_page - 1) // per_page

    history = sorted(
        [(b.as_of_date, Decimal(b.balance)) for b in loan.balance_logs],
        key=lambda t: t[0],
    )
    predicted_series = [(r.due_date.isoformat(), str(r.balance)) for r in schedule.rows[::3]]
    history_series = [(d.isoformat(), str(b)) for d, b in history]

    drift = None
    if history:
        last_date, last_balance = history[-1]
        predicted = predict_balance_at(schedule, last_date)
        if predicted is not None:
            drift = detect_drift(predicted, last_balance)

    return render_template(
        "loans/detail.html",
        loan=loan,
        schedule=schedule,
        rows=rows,
        page=page,
        pages=pages,
        predicted_series=predicted_series,
        history_series=history_series,
        drift=drift,
    )


@bp.route("/<int:loan_id>/edit", methods=["GET", "POST"])
@login_required
def edit_loan(loan_id: int) -> str:
    loan = _get_loan_or_404(loan_id)
    form = LoanForm(obj=loan)
    if form.validate_on_submit():
        loan.name = form.name.data
        loan.lender = form.lender.data or None
        loan.loan_type = LoanType(form.loan_type.data)
        loan.original_principal = form.original_principal.data
        loan.current_rate = form.current_rate.data
        loan.original_term_months = form.original_term_months.data
        loan.payment_amount = form.payment_amount.data
        loan.first_payment_date = form.first_payment_date.data
        loan.payment_day_of_month = form.payment_day_of_month.data
        loan.status = LoanStatus(form.status.data)
        loan.notes = form.notes.data or None
        db.session.commit()
        flash("Loan updated.", "success")
        return redirect(url_for("loans.detail", loan_id=loan.id))
    return render_template("loans/edit.html", form=form, loan=loan)


@bp.route("/<int:loan_id>/delete", methods=["POST"])
@login_required
def delete_loan(loan_id: int) -> str:
    loan = _get_loan_or_404(loan_id)
    db.session.delete(loan)
    db.session.commit()
    flash("Loan deleted.", "info")
    return redirect(url_for("loans.list_loans"))


@bp.route("/<int:loan_id>/log-balance", methods=["GET", "POST"])
@login_required
def log_balance(loan_id: int) -> str:
    loan = _get_loan_or_404(loan_id)
    form = BalanceLogForm()
    if form.validate_on_submit():
        log = BalanceLog(
            loan_id=loan.id,
            as_of_date=form.as_of_date.data,
            balance=form.balance.data,
            notes=form.notes.data or None,
        )
        db.session.add(log)
        db.session.commit()
        flash("Balance logged.", "success")
        return redirect(url_for("loans.detail", loan_id=loan.id))
    return render_template("loans/log_balance.html", form=form, loan=loan)


@bp.route("/<int:loan_id>/recalibrate", methods=["POST"])
@login_required
def recalibrate(loan_id: int) -> str:
    """Re-amortize the remaining term using the latest logged balance.

    The 'red drift' one-click action.
    """
    loan = _get_loan_or_404(loan_id)
    latest = max(loan.balance_logs, key=lambda b: b.as_of_date, default=None)
    if latest is None:
        flash("Log a balance first before recalibrating.", "error")
        return redirect(url_for("loans.detail", loan_id=loan.id))

    months_elapsed = (latest.as_of_date.year - loan.first_payment_date.year) * 12 + (
        latest.as_of_date.month - loan.first_payment_date.month
    )
    remaining_term = max(1, loan.original_term_months - months_elapsed)
    from app.services.amortization import fixed_payment

    new_payment = fixed_payment(Decimal(latest.balance), Decimal(loan.current_rate), remaining_term)
    loan.payment_amount = new_payment
    db.session.commit()
    flash(f"Recalibrated. New payment: ${new_payment}", "success")
    return redirect(url_for("loans.detail", loan_id=loan.id))


@bp.route("/<int:loan_id>/extras", methods=["GET", "POST"])
@login_required
def manage_extras(loan_id: int) -> str:
    loan = _get_loan_or_404(loan_id)
    form = ExtraPaymentForm()
    if form.validate_on_submit():
        ep = ExtraPayment(
            loan_id=loan.id,
            payment_type=ExtraPaymentType(form.payment_type.data),
            amount=form.amount.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            frequency=ExtraPaymentFrequency(form.frequency.data) if form.frequency.data else None,
            notes=form.notes.data or None,
        )
        db.session.add(ep)
        db.session.commit()
        flash("Extra payment added.", "success")
        return redirect(url_for("loans.manage_extras", loan_id=loan.id))
    return render_template("loans/extras.html", form=form, loan=loan)


@bp.route("/<int:loan_id>/extras/<int:extra_id>/delete", methods=["POST"])
@login_required
def delete_extra(loan_id: int, extra_id: int) -> str:
    loan = _get_loan_or_404(loan_id)
    ep = next((e for e in loan.extra_payments if e.id == extra_id), None)
    if ep is None:
        abort(404)
    db.session.delete(ep)
    db.session.commit()
    return redirect(url_for("loans.manage_extras", loan_id=loan.id))


@bp.route("/strategy", methods=["GET", "POST"])
@login_required
def strategy() -> str:
    form = StrategyForm()
    comparison = None
    if form.validate_on_submit():
        loans = (
            db.session.execute(current_user_query(Loan).where(Loan.status == LoanStatus.ACTIVE))
            .scalars()
            .all()
        )
        strategy_loans = []
        for loan in loans:
            balance, _ = _current_balance(loan)
            strategy_loans.append(
                StrategyLoan(
                    id=loan.id,
                    name=loan.name,
                    current_balance=balance,
                    annual_rate=Decimal(loan.current_rate),
                    minimum_payment=Decimal(loan.payment_amount),
                    next_payment_date=loan.first_payment_date,
                )
            )
        comparison = compare_strategies(strategy_loans, form.monthly_extra_budget.data)
    return render_template("loans/strategy.html", form=form, comparison=comparison)
