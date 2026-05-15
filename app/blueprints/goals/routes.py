"""Savings goal routes."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import login_required
from flask_wtf import FlaskForm
from wtforms import DateField, DecimalField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.extensions import db
from app.models import SavingsGoal, current_user_id, current_user_query

bp = Blueprint("goals", __name__, url_prefix="/goals", template_folder="../../templates/goals")


class GoalForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=120)])
    target_amount = DecimalField(
        "Target amount", validators=[DataRequired(), NumberRange(min=0)], places=2
    )
    current_amount = DecimalField(
        "Current amount",
        validators=[Optional(), NumberRange(min=0)],
        places=2,
        default=Decimal("0"),
    )
    target_date = DateField("Target date", validators=[Optional()])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=500)])


def _get_goal(goal_id: int) -> SavingsGoal:
    g = db.session.execute(
        current_user_query(SavingsGoal).where(SavingsGoal.id == goal_id)
    ).scalar_one_or_none()
    if g is None:
        abort(404)
    return g


@bp.route("/")
@login_required
def list_goals() -> str:
    goals = (
        db.session.execute(current_user_query(SavingsGoal).order_by(SavingsGoal.target_date))
        .scalars()
        .all()
    )
    return render_template("goals/list.html", goals=goals, today=date.today())


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_goal() -> str:
    form = GoalForm()
    if form.validate_on_submit():
        goal = SavingsGoal(
            user_id=current_user_id(),
            name=form.name.data,
            target_amount=form.target_amount.data,
            current_amount=form.current_amount.data or Decimal("0"),
            target_date=form.target_date.data,
            notes=form.notes.data or None,
        )
        db.session.add(goal)
        db.session.commit()
        flash("Goal created.", "success")
        return redirect(url_for("goals.list_goals"))
    return render_template("goals/edit.html", form=form, goal=None)


@bp.route("/<int:goal_id>/edit", methods=["GET", "POST"])
@login_required
def edit_goal(goal_id: int) -> str:
    goal = _get_goal(goal_id)
    form = GoalForm(obj=goal)
    if form.validate_on_submit():
        goal.name = form.name.data
        goal.target_amount = form.target_amount.data
        goal.current_amount = form.current_amount.data or Decimal("0")
        goal.target_date = form.target_date.data
        goal.notes = form.notes.data or None
        db.session.commit()
        flash("Goal updated.", "success")
        return redirect(url_for("goals.list_goals"))
    return render_template("goals/edit.html", form=form, goal=goal)


@bp.route("/<int:goal_id>/delete", methods=["POST"])
@login_required
def delete_goal(goal_id: int) -> str:
    goal = _get_goal(goal_id)
    db.session.delete(goal)
    db.session.commit()
    flash("Goal deleted.", "info")
    return redirect(url_for("goals.list_goals"))
