"""budget tables, bill→category link, loan recalibration + day-count fields

Revision ID: 0003_budget_and_loan_fields
Revises: 0002_modules
Create Date: 2026-05-15

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_budget_and_loan_fields"
down_revision = "0002_modules"
branch_labels = None
depends_on = None


_TXN_SOURCE = ("manual", "auto_bill")


def upgrade() -> None:
    # budget_categories first — bills.default_budget_category_id references it.
    op.create_table(
        "budget_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("monthly_limit", sa.Numeric(12, 2), nullable=False),
        sa.Column("color", sa.String(9), nullable=False, server_default="#38bdf8"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_budget_categories_user_name"),
    )
    op.create_index("ix_budget_categories_user_id", "budget_categories", ["user_id"])

    op.create_table(
        "budget_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("budget_categories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("note", sa.String(200)),
        sa.Column(
            "source",
            sa.Enum(*_TXN_SOURCE, name="transaction_source", native_enum=False, length=20),
            nullable=False,
            server_default="manual",
        ),
    )
    op.create_index("ix_budget_transactions_user_id", "budget_transactions", ["user_id"])
    op.create_index("ix_budget_transactions_category_id", "budget_transactions", ["category_id"])
    op.create_index("ix_budget_transactions_date", "budget_transactions", ["date"])

    # bills.default_budget_category_id
    with op.batch_alter_table("bills") as batch:
        batch.add_column(sa.Column("default_budget_category_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_bills_default_budget_category_id",
            "budget_categories",
            ["default_budget_category_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_bills_default_budget_category_id", "bills", ["default_budget_category_id"])

    # loans: day count + recalibration anchors
    with op.batch_alter_table("loans") as batch:
        batch.add_column(
            sa.Column(
                "day_count_convention",
                sa.String(20),
                nullable=False,
                server_default="30/360",
            )
        )
        batch.add_column(sa.Column("recalibration_balance", sa.Numeric(12, 2), nullable=True))
        batch.add_column(sa.Column("recalibration_date", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("loans") as batch:
        batch.drop_column("recalibration_date")
        batch.drop_column("recalibration_balance")
        batch.drop_column("day_count_convention")

    op.drop_index("ix_bills_default_budget_category_id", table_name="bills")
    with op.batch_alter_table("bills") as batch:
        batch.drop_constraint("fk_bills_default_budget_category_id", type_="foreignkey")
        batch.drop_column("default_budget_category_id")

    op.drop_table("budget_transactions")
    op.drop_table("budget_categories")
