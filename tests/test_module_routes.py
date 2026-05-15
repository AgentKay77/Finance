"""Route-level tests for budget, snapshot isolation, and recalibration drift fix."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.extensions import db
from app.models import (
    BalanceLog,
    Bill,
    BillRecurrence,
    BudgetCategory,
    BudgetTransaction,
    Loan,
    LoanStatus,
    LoanType,
    NetWorthSnapshot,
    TransactionSource,
    User,
)


def _make_user(app: Flask, email: str, password: str = "test-pass-1") -> int:
    """Create a user directly in the DB and return its id."""
    with app.app_context():
        user = User(email=email, display_name=email.split("@")[0])
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user.id


def _register_user(client: FlaskClient, email: str, password: str = "test-pass-1") -> None:
    # Clear any existing session first so the route doesn't redirect.
    client.post("/auth/logout")
    client.post(
        "/auth/register",
        data={
            "display_name": email.split("@")[0],
            "email": email,
            "password": password,
            "confirm": password,
        },
        follow_redirects=False,
    )


def _login(client: FlaskClient, email: str, password: str = "test-pass-1") -> None:
    client.post("/auth/logout")
    client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


# ---------- Budget category + transaction CRUD ----------


def test_budget_category_crud_roundtrip(app: Flask, client: FlaskClient) -> None:
    _register_user(client, "budget@example.com")
    _login(client, "budget@example.com")

    resp = client.post(
        "/budget/categories/new",
        data={
            "name": "Groceries",
            "monthly_limit": "600.00",
            "color": "#38bdf8",
            "sort_order": "0",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    with app.app_context():
        cat = db.session.query(BudgetCategory).filter_by(name="Groceries").one()
        assert cat.monthly_limit == Decimal("600.00")


def test_budget_transaction_crud_roundtrip(app: Flask, client: FlaskClient) -> None:
    _register_user(client, "txn@example.com")
    _login(client, "txn@example.com")

    client.post(
        "/budget/categories/new",
        data={"name": "Dining", "monthly_limit": "200", "color": "#facc15", "sort_order": "0"},
    )

    with app.app_context():
        cat_id = db.session.query(BudgetCategory).filter_by(name="Dining").one().id

    resp = client.post(
        "/budget/transactions/",
        data={
            "category_id": str(cat_id),
            "amount": "42.50",
            "txn_date": date.today().isoformat(),
            "note": "Test dinner",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    with app.app_context():
        txns = db.session.query(BudgetTransaction).filter_by(category_id=cat_id).all()
        assert len(txns) == 1
        assert txns[0].amount == Decimal("42.50")
        assert txns[0].source == TransactionSource.MANUAL


def test_delete_category_refuses_when_transactions_exist(app: Flask, client: FlaskClient) -> None:
    _register_user(client, "refuse@example.com")
    _login(client, "refuse@example.com")
    client.post(
        "/budget/categories/new",
        data={"name": "Gas", "monthly_limit": "150", "color": "#4ade80", "sort_order": "0"},
    )
    with app.app_context():
        cat_id = db.session.query(BudgetCategory).filter_by(name="Gas").one().id
    client.post(
        "/budget/transactions/",
        data={
            "category_id": str(cat_id),
            "amount": "50",
            "txn_date": date.today().isoformat(),
            "note": "Fill up",
        },
    )
    resp = client.post(f"/budget/categories/{cat_id}/delete", follow_redirects=True)
    assert b"Reassign" in resp.data
    with app.app_context():
        assert db.session.query(BudgetCategory).filter_by(id=cat_id).count() == 1


# ---------- Bills auto-create budget transaction ----------


def test_marking_bill_paid_auto_creates_transaction(app: Flask, client: FlaskClient) -> None:
    _register_user(client, "auto@example.com")
    _login(client, "auto@example.com")
    client.post(
        "/budget/categories/new",
        data={"name": "Utilities", "monthly_limit": "300", "color": "#38bdf8", "sort_order": "0"},
    )

    with app.app_context():
        user = db.session.query(User).filter_by(email="auto@example.com").one()
        cat = db.session.query(BudgetCategory).filter_by(user_id=user.id).one()
        bill = Bill(
            user_id=user.id,
            name="Electric",
            amount=Decimal("145.00"),
            recurrence=BillRecurrence.MONTHLY,
            next_due_date=date.today(),
            default_budget_category_id=cat.id,
        )
        db.session.add(bill)
        db.session.commit()
        bill_id = bill.id
        cat_id = cat.id

    resp = client.post(f"/bills/{bill_id}/paid", follow_redirects=False)
    assert resp.status_code == 302
    with app.app_context():
        txns = db.session.query(BudgetTransaction).filter_by(category_id=cat_id).all()
        assert len(txns) == 1
        assert txns[0].amount == Decimal("145.00")
        assert txns[0].source == TransactionSource.AUTO_BILL
        assert txns[0].note == "Electric"


def test_marking_bill_paid_without_default_category_does_nothing(
    app: Flask, client: FlaskClient
) -> None:
    _register_user(client, "noauto@example.com")
    _login(client, "noauto@example.com")

    with app.app_context():
        user = db.session.query(User).filter_by(email="noauto@example.com").one()
        bill = Bill(
            user_id=user.id,
            name="HOA",
            amount=Decimal("250"),
            recurrence=BillRecurrence.QUARTERLY,
            next_due_date=date.today(),
        )
        db.session.add(bill)
        db.session.commit()
        bill_id = bill.id

    client.post(f"/bills/{bill_id}/paid")
    with app.app_context():
        assert db.session.query(BudgetTransaction).count() == 0


# ---------- Net worth snapshot isolation ----------


def test_user_cannot_delete_other_users_snapshot(app: Flask, client: FlaskClient) -> None:
    _make_user(app, "alice@example.com")
    _make_user(app, "bob@example.com")

    with app.app_context():
        alice = db.session.query(User).filter_by(email="alice@example.com").one()
        bob = db.session.query(User).filter_by(email="bob@example.com").one()
        alice_snap = NetWorthSnapshot(
            user_id=alice.id,
            snapshot_date=date.today(),
            assets_total=Decimal("1000"),
            liabilities_total=Decimal("500"),
            net_worth=Decimal("500"),
        )
        bob_snap = NetWorthSnapshot(
            user_id=bob.id,
            snapshot_date=date.today(),
            assets_total=Decimal("2000"),
            liabilities_total=Decimal("0"),
            net_worth=Decimal("2000"),
        )
        db.session.add_all([alice_snap, bob_snap])
        db.session.commit()
        alice_snap_id = alice_snap.id
        bob_snap_id = bob_snap.id

    # Bob signs in and tries to delete Alice's snapshot.
    _login(client, "bob@example.com")
    resp = client.post(f"/networth/snapshots/{alice_snap_id}/delete")
    assert resp.status_code == 404

    # Bob's own snapshot deletes fine.
    resp = client.post(f"/networth/snapshots/{bob_snap_id}/delete", follow_redirects=False)
    assert resp.status_code == 302
    with app.app_context():
        assert db.session.query(NetWorthSnapshot).filter_by(id=bob_snap_id).count() == 0
        # Alice's snapshot must be untouched.
        assert db.session.query(NetWorthSnapshot).filter_by(id=alice_snap_id).count() == 1


# ---------- Recalibrate flips drift back to green ----------


def test_recalibrate_persists_anchor_and_clears_red_drift(app: Flask, client: FlaskClient) -> None:
    _register_user(client, "drift@example.com")
    _login(client, "drift@example.com")

    with app.app_context():
        user = db.session.query(User).filter_by(email="drift@example.com").one()
        loan = Loan(
            user_id=user.id,
            name="Mortgage",
            loan_type=LoanType.MORTGAGE,
            original_principal=Decimal("300000"),
            current_rate=Decimal("0.06"),
            original_term_months=360,
            payment_amount=Decimal("1798.65"),
            first_payment_date=date(2024, 1, 1),
            payment_day_of_month=1,
            status=LoanStatus.ACTIVE,
        )
        db.session.add(loan)
        db.session.commit()
        # Log a balance way off from prediction → triggers red drift.
        db.session.add(
            BalanceLog(
                loan_id=loan.id,
                as_of_date=date(2026, 5, 1),
                balance=Decimal("260000"),
            )
        )
        db.session.commit()
        loan_id = loan.id

    # Before recalibrate, drift is severe (≈10% off).
    from app.services.amortization import (
        LoanTerms,
        build_schedule,
        detect_drift,
        predict_balance_at,
    )

    with app.app_context():
        loan = db.session.get(Loan, loan_id)
        terms = LoanTerms(
            principal=Decimal(loan.original_principal),
            annual_rate=Decimal(loan.current_rate),
            term_months=loan.original_term_months,
            payment_amount=Decimal(loan.payment_amount),
            first_payment_date=loan.first_payment_date,
        )
        sched = build_schedule(terms)
        predicted = predict_balance_at(sched, date(2026, 5, 1))
        drift_before = detect_drift(predicted, Decimal("260000"))
        assert drift_before.severity == "red"

    resp = client.post(f"/loans/{loan_id}/recalibrate", follow_redirects=False)
    assert resp.status_code == 302

    # After recalibrate the loan has anchor fields set; rebuilding the
    # schedule from those anchors makes predicted == logged → green.
    with app.app_context():
        loan = db.session.get(Loan, loan_id)
        assert loan.recalibration_balance == Decimal("260000.00")
        assert loan.recalibration_date == date(2026, 5, 1)
        terms = LoanTerms(
            principal=Decimal(loan.original_principal),
            annual_rate=Decimal(loan.current_rate),
            term_months=loan.original_term_months,
            payment_amount=Decimal(loan.payment_amount),
            first_payment_date=loan.first_payment_date,
        )
        sched = build_schedule(
            terms,
            starting_balance=Decimal(loan.recalibration_balance),
            starting_date=loan.recalibration_date,
        )
        # Predicted on the anchor date is exactly the logged balance →
        # zero delta → green.
        predicted = predict_balance_at(sched, date(2026, 5, 1)) or Decimal(loan.original_principal)
        drift_after = detect_drift(predicted, Decimal("260000"))
        assert drift_after.severity == "green"


@pytest.fixture
def app(tmp_path):
    """Override the smoke-test fixture to share fresh schema per test."""
    from app import create_app
    from app.config import TestingConfig

    application = create_app(TestingConfig)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
