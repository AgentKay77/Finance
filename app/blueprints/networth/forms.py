"""Forms for assets and net worth."""

from __future__ import annotations

from datetime import date

from flask_wtf import FlaskForm
from wtforms import DateField, DecimalField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.models.asset import AssetType


class AssetForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=120)])
    asset_type = SelectField("Type", choices=[(t.value, t.value) for t in AssetType])
    current_value = DecimalField(
        "Current value", validators=[DataRequired(), NumberRange(min=0)], places=2
    )
    as_of_date = DateField("As of", validators=[DataRequired()], default=date.today)
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=500)])
