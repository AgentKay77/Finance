"""Forms for budget categories and transactions."""

from __future__ import annotations

import re
from datetime import date

from flask_wtf import FlaskForm
from wtforms import DateField, DecimalField, IntegerField, SelectField, StringField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, Regexp

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


class CategoryForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=80)])
    monthly_limit = DecimalField(
        "Monthly limit", validators=[DataRequired(), NumberRange(min=0)], places=2
    )
    color = StringField(
        "Color (hex like #38bdf8)",
        validators=[DataRequired(), Regexp(HEX_COLOR, message="Use #RRGGBB hex format.")],
        default="#38bdf8",
    )
    sort_order = IntegerField("Sort order", default=0, validators=[Optional()])


class TransactionForm(FlaskForm):
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])
    amount = DecimalField("Amount", validators=[DataRequired(), NumberRange(min=0)], places=2)
    txn_date = DateField("Date", validators=[DataRequired()], default=date.today)
    note = StringField("Note", validators=[Optional(), Length(max=200)])
