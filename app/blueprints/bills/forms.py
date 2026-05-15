"""Forms for the bills module."""

from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, DecimalField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.models.bill import BillRecurrence


class BillForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=120)])
    amount = DecimalField("Amount", validators=[DataRequired(), NumberRange(min=0)], places=2)
    recurrence = SelectField("Recurrence", choices=[(r.value, r.value) for r in BillRecurrence])
    next_due_date = DateField("Next due date", validators=[DataRequired()])
    end_date = DateField("End date", validators=[Optional()])
    autopay = BooleanField("Autopay")
    category = StringField("Category", validators=[Optional(), Length(max=60)])
    default_budget_category_id = SelectField(
        "Default budget category (auto-creates a transaction on mark-paid)",
        coerce=lambda v: int(v) if v else None,
        validators=[Optional()],
    )
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=500)])
