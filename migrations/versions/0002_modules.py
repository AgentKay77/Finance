"""loans, assets, bills, goals, subscriptions, snapshots

Revision ID: 0002_modules
Revises: 0001_initial_users
Create Date: 2026-05-08

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_modules"
down_revision = "0001_initial_users"
branch_labels = None
depends_on = None


_LOAN_TYPES = ("mortgage", "auto", "student", "personal", "credit_card", "other")
_LOAN_STATUS = ("active", "paid_off", "closed")
_BAL_SOURCE = ("manual", "statement", "computed")
_EP_TYPE = ("one_time", "recurring")
_EP_FREQ = ("monthly", "biweekly", "annual")
_ASSET_TYPE = ("cash", "investment", "real_estate", "vehicle", "other")
_BILL_REC = ("monthly", "biweekly", "weekly", "annual", "quarterly", "one_time")
_BILL_CYC = ("monthly", "annual", "quarterly", "weekly")


def upgrade() -> None:
    op.create_table(
        "loans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("lender", sa.String(120)),
        sa.Column(
            "loan_type",
            sa.Enum(*_LOAN_TYPES, name="loan_type", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("original_principal", sa.Numeric(12, 2), nullable=False),
        sa.Column("current_rate", sa.Numeric(7, 5), nullable=False),
        sa.Column("original_term_months", sa.Integer(), nullable=False),
        sa.Column("payment_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("first_payment_date", sa.Date(), nullable=False),
        sa.Column("payment_day_of_month", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(*_LOAN_STATUS, name="loan_status", native_enum=False, length=20),
            nullable=False,
            server_default="active",
        ),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_loans_user_id", "loans", ["user_id"])

    op.create_table(
        "balance_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "loan_id", sa.Integer(), sa.ForeignKey("loans.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("balance", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "source",
            sa.Enum(*_BAL_SOURCE, name="balance_source", native_enum=False, length=20),
            nullable=False,
            server_default="manual",
        ),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_balance_logs_loan_id", "balance_logs", ["loan_id"])

    op.create_table(
        "scheduled_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "loan_id", sa.Integer(), sa.ForeignKey("loans.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("scheduled_principal", sa.Numeric(12, 2), nullable=False),
        sa.Column("scheduled_interest", sa.Numeric(12, 2), nullable=False),
        sa.Column("scheduled_balance", sa.Numeric(12, 2), nullable=False),
    )
    op.create_index("ix_scheduled_payments_loan_id", "scheduled_payments", ["loan_id"])

    op.create_table(
        "extra_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "loan_id", sa.Integer(), sa.ForeignKey("loans.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "payment_type",
            sa.Enum(*_EP_TYPE, name="extra_payment_type", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date()),
        sa.Column(
            "frequency",
            sa.Enum(*_EP_FREQ, name="extra_payment_frequency", native_enum=False, length=20),
        ),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_extra_payments_loan_id", "extra_payments", ["loan_id"])

    op.create_table(
        "rate_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "loan_id", sa.Integer(), sa.ForeignKey("loans.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("new_rate", sa.Numeric(7, 5), nullable=False),
    )
    op.create_index("ix_rate_changes_loan_id", "rate_changes", ["loan_id"])

    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column(
            "asset_type",
            sa.Enum(*_ASSET_TYPE, name="asset_type", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("current_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assets_user_id", "assets", ["user_id"])

    op.create_table(
        "net_worth_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("assets_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("liabilities_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("net_worth", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_net_worth_snapshots_user_id", "net_worth_snapshots", ["user_id"])
    op.create_index(
        "ix_net_worth_snapshots_snapshot_date", "net_worth_snapshots", ["snapshot_date"]
    )

    op.create_table(
        "bills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "recurrence",
            sa.Enum(*_BILL_REC, name="bill_recurrence", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("next_due_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date()),
        sa.Column("autopay", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("category", sa.String(60)),
        sa.Column("notes", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bills_user_id", "bills", ["user_id"])

    op.create_table(
        "savings_goals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("target_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("current_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("target_date", sa.Date()),
        sa.Column("notes", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_savings_goals_user_id", "savings_goals", ["user_id"])

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "billing_cycle",
            sa.Enum(*_BILL_CYC, name="billing_cycle", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("next_renewal_date", sa.Date(), nullable=False),
        sa.Column("category", sa.String(60)),
        sa.Column("notes", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])


def downgrade() -> None:
    for tbl in (
        "subscriptions",
        "savings_goals",
        "bills",
        "net_worth_snapshots",
        "assets",
        "rate_changes",
        "extra_payments",
        "scheduled_payments",
        "balance_logs",
        "loans",
    ):
        op.drop_table(tbl)
