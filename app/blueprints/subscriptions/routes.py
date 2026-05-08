"""Subscription tracker routes."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import login_required
from flask_wtf import FlaskForm
from wtforms import DateField, DecimalField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.extensions import db
from app.models import Subscription, current_user_id, current_user_query
from app.models.subscription import BillingCycle
from app.services.recurrence import advance_due_date

bp = Blueprint(
    "subscriptions",
    __name__,
    url_prefix="/subscriptions",
    template_folder="../../templates/subscriptions",
)


# Map BillingCycle → recurrence string used by the recurrence engine.
_CYCLE_TO_RECURRENCE = {
    BillingCycle.MONTHLY: "monthly",
    BillingCycle.ANNUAL: "annual",
    BillingCycle.QUARTERLY: "quarterly",
    BillingCycle.WEEKLY: "weekly",
}


class SubscriptionForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=120)])
    amount = DecimalField("Amount", validators=[DataRequired(), NumberRange(min=0)], places=2)
    billing_cycle = SelectField("Billing cycle", choices=[(c.value, c.value) for c in BillingCycle])
    next_renewal_date = DateField("Next renewal", validators=[DataRequired()])
    category = StringField("Category", validators=[Optional(), Length(max=60)])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=500)])


def _get_sub(sub_id: int) -> Subscription:
    sub = db.session.execute(
        current_user_query(Subscription).where(Subscription.id == sub_id)
    ).scalar_one_or_none()
    if sub is None:
        abort(404)
    return sub


def _monthly_equivalent(sub: Subscription) -> Decimal:
    cycle = sub.billing_cycle
    amt = Decimal(sub.amount)
    if cycle == BillingCycle.MONTHLY:
        return amt
    if cycle == BillingCycle.ANNUAL:
        return (amt / Decimal(12)).quantize(Decimal("0.01"))
    if cycle == BillingCycle.QUARTERLY:
        return (amt / Decimal(3)).quantize(Decimal("0.01"))
    if cycle == BillingCycle.WEEKLY:
        return (amt * Decimal("4.345")).quantize(Decimal("0.01"))
    return amt


@bp.route("/")
@login_required
def list_subs() -> str:
    subs = (
        db.session.execute(
            current_user_query(Subscription).order_by(Subscription.next_renewal_date)
        )
        .scalars()
        .all()
    )
    monthly_total = sum((_monthly_equivalent(s) for s in subs), Decimal("0"))
    annual_total = monthly_total * Decimal(12)
    return render_template(
        "subscriptions/list.html",
        subs=subs,
        monthly_total=monthly_total,
        annual_total=annual_total,
        today=date.today(),
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_sub() -> str:
    form = SubscriptionForm()
    if form.validate_on_submit():
        sub = Subscription(
            user_id=current_user_id(),
            name=form.name.data,
            amount=form.amount.data,
            billing_cycle=BillingCycle(form.billing_cycle.data),
            next_renewal_date=form.next_renewal_date.data,
            category=form.category.data or None,
            notes=form.notes.data or None,
        )
        db.session.add(sub)
        db.session.commit()
        flash("Subscription added.", "success")
        return redirect(url_for("subscriptions.list_subs"))
    return render_template("subscriptions/edit.html", form=form, sub=None)


@bp.route("/<int:sub_id>/edit", methods=["GET", "POST"])
@login_required
def edit_sub(sub_id: int) -> str:
    sub = _get_sub(sub_id)
    form = SubscriptionForm(obj=sub)
    if form.validate_on_submit():
        sub.name = form.name.data
        sub.amount = form.amount.data
        sub.billing_cycle = BillingCycle(form.billing_cycle.data)
        sub.next_renewal_date = form.next_renewal_date.data
        sub.category = form.category.data or None
        sub.notes = form.notes.data or None
        db.session.commit()
        flash("Subscription updated.", "success")
        return redirect(url_for("subscriptions.list_subs"))
    return render_template("subscriptions/edit.html", form=form, sub=sub)


@bp.route("/<int:sub_id>/renewed", methods=["POST"])
@login_required
def renewed(sub_id: int) -> str:
    sub = _get_sub(sub_id)
    sub.next_renewal_date = advance_due_date(
        sub.next_renewal_date, _CYCLE_TO_RECURRENCE[sub.billing_cycle]
    )
    db.session.commit()
    flash(f"{sub.name} renewed; next on {sub.next_renewal_date}.", "success")
    return redirect(url_for("subscriptions.list_subs"))


@bp.route("/<int:sub_id>/delete", methods=["POST"])
@login_required
def delete_sub(sub_id: int) -> str:
    sub = _get_sub(sub_id)
    db.session.delete(sub)
    db.session.commit()
    flash("Subscription deleted.", "info")
    return redirect(url_for("subscriptions.list_subs"))
