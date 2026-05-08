"""Payoff what-if scenario routes (Phase 5)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from flask import Blueprint, abort, render_template, request
from flask_login import login_required

from app.extensions import db
from app.models import Loan, current_user_query
from app.services.amortization import (
    LoanTerms,
    build_schedule,
)
from app.services.whatif import WhatIfScenario, run_scenario

bp = Blueprint("whatif", __name__, url_prefix="/whatif", template_folder="../../templates/whatif")


def _terms(loan: Loan) -> LoanTerms:
    return LoanTerms(
        principal=Decimal(loan.original_principal),
        annual_rate=Decimal(loan.current_rate),
        term_months=loan.original_term_months,
        payment_amount=Decimal(loan.payment_amount),
        first_payment_date=loan.first_payment_date,
    )


def _parse_decimal(raw: str | None, default: Decimal = Decimal("0")) -> Decimal:
    if not raw:
        return default
    try:
        return Decimal(raw)
    except Exception:
        return default


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


@bp.route("/")
@login_required
def index() -> str:
    loans = db.session.execute(current_user_query(Loan).order_by(Loan.name)).scalars().all()
    return render_template("whatif/index.html", loans=loans)


@bp.route("/<int:loan_id>", methods=["GET", "POST"])
@login_required
def scenario(loan_id: int) -> str:
    loan = db.session.execute(
        current_user_query(Loan).where(Loan.id == loan_id)
    ).scalar_one_or_none()
    if loan is None:
        abort(404)

    terms = _terms(loan)
    baseline = build_schedule(terms)

    results = []
    if request.method == "POST":
        extra = _parse_decimal(request.form.get("extra_monthly"), Decimal("0"))
        one_time = _parse_decimal(request.form.get("one_time_amount"), Decimal("0"))
        one_time_date = _parse_date(request.form.get("one_time_date"))
        rate_override = (
            _parse_decimal(request.form.get("rate_override"))
            if request.form.get("rate_override")
            else None
        )
        rate_override_date = _parse_date(request.form.get("rate_override_date"))

        if extra > 0:
            results.append(
                run_scenario(
                    terms,
                    baseline,
                    WhatIfScenario(
                        label=f"+${extra}/mo",
                        extra_monthly=extra,
                    ),
                )
            )
        if one_time > 0 and one_time_date:
            results.append(
                run_scenario(
                    terms,
                    baseline,
                    WhatIfScenario(
                        label=f"${one_time} on {one_time_date}",
                        one_time_amount=one_time,
                        one_time_date=one_time_date,
                    ),
                )
            )
        if rate_override is not None and rate_override_date:
            results.append(
                run_scenario(
                    terms,
                    baseline,
                    WhatIfScenario(
                        label=f"Refi to {rate_override} on {rate_override_date}",
                        rate_override=rate_override,
                        rate_override_date=rate_override_date,
                    ),
                )
            )
        if extra > 0 and one_time > 0 and one_time_date:
            results.append(
                run_scenario(
                    terms,
                    baseline,
                    WhatIfScenario(
                        label="Combined: monthly + lump",
                        extra_monthly=extra,
                        one_time_amount=one_time,
                        one_time_date=one_time_date,
                    ),
                )
            )

    return render_template(
        "whatif/scenario.html",
        loan=loan,
        baseline=baseline,
        results=results,
    )
