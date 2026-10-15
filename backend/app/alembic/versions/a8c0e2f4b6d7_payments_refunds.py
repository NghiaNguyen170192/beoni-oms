"""Payments, refunds, and seeded payment methods

Revision ID: a8c0e2f4b6d7
Revises: f7a9c1e3b5d6
Create Date: 2026-10-15 12:45:00.000000

"""

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

revision = "a8c0e2f4b6d7"
down_revision = "f7a9c1e3b5d6"
branch_labels = None
depends_on = None

CASH_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
BANK_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")


def upgrade():
    op.create_table(
        "payment_methods",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('cash', 'bank_transfer', 'other')",
            name="ck_payment_methods_kind",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_payment_methods_name", "payment_methods", ["name"], unique=True
    )
    now = datetime.now(timezone.utc)
    payment_methods = sa.table(
        "payment_methods",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("kind", sa.String()),
        sa.column("is_active", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        payment_methods,
        [
            {
                "id": CASH_ID,
                "name": "Cash",
                "kind": "cash",
                "is_active": True,
                "created_at": now,
            },
            {
                "id": BANK_ID,
                "name": "Bank transfer",
                "kind": "bank_transfer",
                "is_active": True,
                "created_at": now,
            },
        ],
    )
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("method_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("tendered", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("change_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("reference", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("void_reason", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("recorded_by_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("voided_by_id", sa.Uuid(), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_payments_amount"),
        sa.CheckConstraint(
            "status IN ('active', 'voided')", name="ck_payments_status"
        ),
        sa.CheckConstraint(
            "(status = 'voided') = (voided_at IS NOT NULL)",
            name="ck_payments_voided_at",
        ),
        sa.CheckConstraint(
            "tendered IS NULL OR (tendered >= amount AND change_amount = tendered - amount)",
            name="ck_payments_tender",
        ),
        sa.ForeignKeyConstraint(["method_id"], ["payment_methods.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["voided_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payments_order", "payments", ["order_id"], unique=False)
    op.create_index("ix_payments_recorded_at", "payments", ["recorded_at"], unique=False)
    op.create_table(
        "refunds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("method_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("reason", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("reference", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
        sa.Column("recorded_by_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_refunds_amount"),
        sa.ForeignKeyConstraint(["method_id"], ["payment_methods.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_refunds_order", "refunds", ["order_id"], unique=False)
    op.create_index("ix_refunds_recorded_at", "refunds", ["recorded_at"], unique=False)
    op.create_table(
        "refund_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("refund_id", sa.Uuid(), nullable=False),
        sa.Column("order_line_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_refund_lines_quantity"),
        sa.CheckConstraint("amount >= 0", name="ck_refund_lines_amount"),
        sa.ForeignKeyConstraint(["order_line_id"], ["order_lines.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["refund_id"], ["refunds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_refund_lines_refund", "refund_lines", ["refund_id"], unique=False)


def downgrade():
    op.drop_index("ix_refund_lines_refund", table_name="refund_lines")
    op.drop_table("refund_lines")
    op.drop_index("ix_refunds_recorded_at", table_name="refunds")
    op.drop_index("ix_refunds_order", table_name="refunds")
    op.drop_table("refunds")
    op.drop_index("ix_payments_recorded_at", table_name="payments")
    op.drop_index("ix_payments_order", table_name="payments")
    op.drop_table("payments")
    op.drop_index("uq_payment_methods_name", table_name="payment_methods")
    op.drop_table("payment_methods")
