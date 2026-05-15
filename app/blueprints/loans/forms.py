"""Forms for the loan tracker."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    DecimalField,
    IntegerField,
    SelectField,
    StringField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.models import (
    BillingCycle,
    ExtraPaymentFrequency,
    ExtraPaymentType,
    LoanStatus,
    LoanType,
)


class LoanForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=120)])
    lender = StringField("Lender", validators=[Optional(), Length(max=120)])
    loan_type = SelectField("Type", choices=[(t.value, t.value) for t in LoanType])
    original_principal = DecimalField(
        "Original principal", validators=[DataRequired(), NumberRange(min=0)], places=2
    )
    current_rate = DecimalField(
        "APR (e.g. 0.06375)", validators=[DataRequired(), NumberRange(min=0, max=1)], places=5
    )
    original_term_months = IntegerField(
        "Term (months)", validators=[DataRequired(), NumberRange(min=1, max=720)]
    )
    payment_amount = DecimalField(
        "Monthly payment", validators=[DataRequired(), NumberRange(min=0)], places=2
    )
    first_payment_date = DateField("First payment date", validators=[DataRequired()])
    payment_day_of_month = IntegerField(
        "Payment day of month", validators=[DataRequired(), NumberRange(min=1, max=28)], default=1
    )
    status = SelectField(
        "Status", choices=[(s.value, s.value) for s in LoanStatus], default=LoanStatus.ACTIVE.value
    )
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=2000)])


class BalanceLogForm(FlaskForm):
    as_of_date = DateField("As of", validators=[DataRequired()], default=date.today)
    balance = DecimalField("Balance", validators=[DataRequired(), NumberRange(min=0)], places=2)
    notes = StringField("Notes", validators=[Optional(), Length(max=500)])


class ExtraPaymentForm(FlaskForm):
    payment_type = SelectField("Type", choices=[(t.value, t.value) for t in ExtraPaymentType])
    amount = DecimalField("Amount", validators=[DataRequired(), NumberRange(min=0)], places=2)
    start_date = DateField("Start", validators=[DataRequired()])
    end_date = DateField("End (recurring only)", validators=[Optional()])
    frequency = SelectField(
        "Frequency",
        choices=[("", "—")] + [(f.value, f.value) for f in ExtraPaymentFrequency],
        default="",
    )
    notes = StringField("Notes", validators=[Optional(), Length(max=500)])


class StrategyForm(FlaskForm):
    monthly_extra_budget = DecimalField(
        "Monthly extra budget",
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
        default=Decimal("0"),
    )


# kept here so BillingCycle is imported elsewhere too
_ = BillingCycle
