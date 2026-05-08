"""Dashboard / hub home page.

Phase 1 placeholder. Later phases will pull summary widgets from the loan,
net worth, bill, goal, and subscription modules.
"""

from __future__ import annotations

from flask import Blueprint, render_template
from flask_login import login_required

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def home() -> str:
    return render_template("dashboard/home.html")


@bp.route("/healthz")
def healthz() -> tuple[str, int]:
    return "ok", 200
