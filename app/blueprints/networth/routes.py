"""Net worth dashboard routes."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import login_required

from app.blueprints.networth.forms import AssetForm
from app.extensions import db
from app.models import Asset, Loan, NetWorthSnapshot, current_user_id, current_user_query
from app.models.asset import AssetType
from app.services.amortization import LoanTerms as _Terms
from app.services.amortization import (
    build_schedule,
    predict_balance_at,
)
from app.services.networth import compute_breakdown

bp = Blueprint(
    "networth", __name__, url_prefix="/networth", template_folder="../../templates/networth"
)


def _liability_for(loan: Loan) -> Decimal:
    latest = max(loan.balance_logs, key=lambda b: b.as_of_date, default=None)
    if latest is not None:
        return Decimal(latest.balance)
    schedule = build_schedule(
        _Terms(
            principal=Decimal(loan.original_principal),
            annual_rate=Decimal(loan.current_rate),
            term_months=loan.original_term_months,
            payment_amount=Decimal(loan.payment_amount),
            first_payment_date=loan.first_payment_date,
        )
    )
    return predict_balance_at(schedule, date.today()) or Decimal(loan.original_principal)


@bp.route("/")
@login_required
def home() -> str:
    assets = db.session.execute(current_user_query(Asset).order_by(Asset.name)).scalars().all()
    loans = db.session.execute(current_user_query(Loan)).scalars().all()
    asset_rows = [(a.name, Decimal(a.current_value)) for a in assets]
    liability_rows = [(loan.name, _liability_for(loan)) for loan in loans]
    breakdown = compute_breakdown(asset_rows, liability_rows, date.today())

    snapshots = (
        db.session.execute(
            current_user_query(NetWorthSnapshot).order_by(NetWorthSnapshot.snapshot_date)
        )
        .scalars()
        .all()
    )
    trend_series = [(s.snapshot_date.isoformat(), str(s.net_worth)) for s in snapshots]

    return render_template(
        "networth/home.html",
        breakdown=breakdown,
        trend_series=trend_series,
        snapshots=list(reversed(snapshots)),
    )


@bp.route("/snapshots/<int:snapshot_id>/delete", methods=["POST"])
@login_required
def delete_snapshot(snapshot_id: int) -> str:
    """Delete a single NetWorthSnapshot row.

    404s if the snapshot doesn't belong to the current user — we 404 not
    403 so we don't confirm the existence of someone else's snapshot id.
    """
    snap = db.session.execute(
        current_user_query(NetWorthSnapshot).where(NetWorthSnapshot.id == snapshot_id)
    ).scalar_one_or_none()
    if snap is None:
        abort(404)
    db.session.delete(snap)
    db.session.commit()
    flash("Snapshot deleted.", "info")
    return redirect(url_for("networth.home"))


@bp.route("/snapshot", methods=["POST"])
@login_required
def snapshot() -> str:
    """Save the current breakdown as a NetWorthSnapshot row."""
    assets = db.session.execute(current_user_query(Asset)).scalars().all()
    loans = db.session.execute(current_user_query(Loan)).scalars().all()
    asset_rows = [(a.name, Decimal(a.current_value)) for a in assets]
    liability_rows = [(loan.name, _liability_for(loan)) for loan in loans]
    breakdown = compute_breakdown(asset_rows, liability_rows, date.today())
    snap = NetWorthSnapshot(
        user_id=current_user_id(),
        snapshot_date=breakdown.as_of,
        assets_total=breakdown.assets_total,
        liabilities_total=breakdown.liabilities_total,
        net_worth=breakdown.net_worth,
    )
    db.session.add(snap)
    db.session.commit()
    flash(f"Snapshot saved: net worth ${breakdown.net_worth}", "success")
    return redirect(url_for("networth.home"))


@bp.route("/assets")
@login_required
def list_assets() -> str:
    assets = db.session.execute(current_user_query(Asset).order_by(Asset.name)).scalars().all()
    return render_template("networth/assets.html", assets=assets)


@bp.route("/assets/new", methods=["GET", "POST"])
@login_required
def new_asset() -> str:
    form = AssetForm()
    if form.validate_on_submit():
        asset = Asset(
            user_id=current_user_id(),
            name=form.name.data,
            asset_type=AssetType(form.asset_type.data),
            current_value=form.current_value.data,
            as_of_date=form.as_of_date.data,
            notes=form.notes.data or None,
        )
        db.session.add(asset)
        db.session.commit()
        flash("Asset added.", "success")
        return redirect(url_for("networth.list_assets"))
    return render_template("networth/asset_edit.html", form=form, asset=None)


@bp.route("/assets/<int:asset_id>/edit", methods=["GET", "POST"])
@login_required
def edit_asset(asset_id: int) -> str:
    asset = db.session.execute(
        current_user_query(Asset).where(Asset.id == asset_id)
    ).scalar_one_or_none()
    if asset is None:
        abort(404)
    form = AssetForm(obj=asset)
    if form.validate_on_submit():
        asset.name = form.name.data
        asset.asset_type = AssetType(form.asset_type.data)
        asset.current_value = form.current_value.data
        asset.as_of_date = form.as_of_date.data
        asset.notes = form.notes.data or None
        db.session.commit()
        flash("Asset updated.", "success")
        return redirect(url_for("networth.list_assets"))
    return render_template("networth/asset_edit.html", form=form, asset=asset)


@bp.route("/assets/<int:asset_id>/delete", methods=["POST"])
@login_required
def delete_asset(asset_id: int) -> str:
    asset = db.session.execute(
        current_user_query(Asset).where(Asset.id == asset_id)
    ).scalar_one_or_none()
    if asset is None:
        abort(404)
    db.session.delete(asset)
    db.session.commit()
    flash("Asset deleted.", "info")
    return redirect(url_for("networth.list_assets"))
