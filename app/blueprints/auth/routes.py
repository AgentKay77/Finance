"""Authentication routes: register, login, logout."""

from __future__ import annotations

from urllib.parse import urlparse

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import select

from app.blueprints.auth.forms import LoginForm, RegisterForm
from app.extensions import db
from app.models import User

bp = Blueprint("auth", __name__, template_folder="../../templates/auth")


def _safe_next(url: str | None) -> str | None:
    """Reject open-redirect targets (only allow same-host relative URLs)."""

    if not url:
        return None
    parsed = urlparse(url)
    if parsed.netloc or parsed.scheme:
        return None
    if not url.startswith("/"):
        return None
    return url


@bp.route("/register", methods=["GET", "POST"])
def register() -> str:
    if not current_app.config.get("ALLOW_REGISTRATION", True):
        abort(404)
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))

    form = RegisterForm()
    if form.validate_on_submit():
        existing = db.session.execute(
            select(User).where(User.email == form.email.data.lower().strip())
        ).scalar_one_or_none()
        if existing is not None:
            flash("That email is already registered.", "error")
        else:
            user = User(
                email=form.email.data.lower().strip(),
                display_name=form.display_name.data.strip(),
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Welcome aboard.", "success")
            return redirect(url_for("dashboard.home"))

    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login() -> str:
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))

    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.execute(
            select(User).where(User.email == form.email.data.lower().strip())
        ).scalar_one_or_none()
        if user is None or not user.check_password(form.password.data):
            flash("Email or password is incorrect.", "error")
        elif not user.is_active:
            flash("This account is disabled.", "error")
        else:
            login_user(user, remember=form.remember.data)
            target = _safe_next(request.args.get("next")) or url_for("dashboard.home")
            return redirect(target)

    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout() -> str:
    logout_user()
    flash("Signed out.", "info")
    return redirect(url_for("auth.login"))
