"""Suppliers, stock receipts, and supplier payables

Revision ID: f7a9c1e3b5d6
Revises: e6a8c0d2f4b5
Create Date: 2026-10-15 12:20:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


revision = "f7a9c1e3b5d6"
down_revision = "e6a8c0d2f4b5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("code", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column("phone", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("address", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column("tax_code", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True),
        sa.Column(
            "contact_person", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True
        ),
        sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_suppliers_code", "suppliers", ["code"], unique=True)
    op.create_table(
        "receipt_reference_counters",
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("business_date"),
    )
    op.create_table(
        "stock_receipts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reference", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_value", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("posted_by_id", sa.Uuid(), nullable=True),
        sa.Column("reversed_by_id", sa.Uuid(), nullable=True),
        sa.Column("reversal_of_id", sa.Uuid(), nullable=True),
        sa.Column(
            "reversal_reason", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'posted', 'reversed')", name="ck_stock_receipts_status"
        ),
        sa.CheckConstraint(
            "(status = 'draft') = (posted_at IS NULL)", name="ck_stock_receipts_posted_at"
        ),
        sa.CheckConstraint(
            "(status = 'reversed') = (reversed_by_id IS NOT NULL)",
            name="ck_stock_receipts_reversed_by",
        ),
        sa.CheckConstraint(
            "reversal_of_id IS NULL OR status = 'posted'",
            name="ck_stock_receipts_reversal_posted",
        ),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["posted_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["reversed_by_id"], ["stock_receipts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reversal_of_id"], ["stock_receipts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_stock_receipts_reference", "stock_receipts", ["reference"], unique=True
    )
    op.create_index(
        "ix_stock_receipts_supplier", "stock_receipts", ["supplier_id"], unique=False
    )
    op.create_index(
        "ix_stock_receipts_date", "stock_receipts", ["receipt_date"], unique=False
    )
    op.create_table(
        "stock_receipt_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("purchase_qty", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("purchase_unit_cost", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("base_qty", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("base_unit_cost", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("line_total", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.CheckConstraint(
            "purchase_qty <> 0", name="ck_stock_receipt_lines_qty_nonzero"
        ),
        sa.CheckConstraint(
            "purchase_unit_cost >= 0", name="ck_stock_receipt_lines_cost"
        ),
        sa.CheckConstraint("base_qty <> 0", name="ck_stock_receipt_lines_base_qty"),
        sa.CheckConstraint(
            "base_unit_cost >= 0", name="ck_stock_receipt_lines_base_cost"
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id"], ["stock_receipts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["item_id"], ["inventory_items.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_stock_receipt_lines_receipt",
        "stock_receipt_lines",
        ["receipt_id"],
        unique=False,
    )
    op.create_table(
        "supplier_payables",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("paid_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "status IN ('unpaid', 'partially_paid', 'paid', 'cancelled')",
            name="ck_supplier_payables_status",
        ),
        sa.CheckConstraint("amount >= 0", name="ck_supplier_payables_amount"),
        sa.CheckConstraint(
            "paid_amount >= 0 AND paid_amount <= amount",
            name="ck_supplier_payables_paid",
        ),
        sa.CheckConstraint(
            "(status = 'cancelled') "
            "OR (status = 'unpaid' AND paid_amount = 0) "
            "OR (status = 'partially_paid' AND paid_amount > 0 AND paid_amount < amount) "
            "OR (status = 'paid' AND paid_amount = amount AND amount > 0)",
            name="ck_supplier_payables_status_amounts",
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id"], ["stock_receipts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_supplier_payables_receipt", "supplier_payables", ["receipt_id"], unique=True
    )
    op.create_index(
        "ix_supplier_payables_supplier",
        "supplier_payables",
        ["supplier_id"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_supplier_payables_supplier", table_name="supplier_payables")
    op.drop_index("uq_supplier_payables_receipt", table_name="supplier_payables")
    op.drop_table("supplier_payables")
    op.drop_index("ix_stock_receipt_lines_receipt", table_name="stock_receipt_lines")
    op.drop_table("stock_receipt_lines")
    op.drop_index("ix_stock_receipts_date", table_name="stock_receipts")
    op.drop_index("ix_stock_receipts_supplier", table_name="stock_receipts")
    op.drop_index("uq_stock_receipts_reference", table_name="stock_receipts")
    op.drop_table("stock_receipts")
    op.drop_table("receipt_reference_counters")
    op.drop_index("uq_suppliers_code", table_name="suppliers")
    op.drop_table("suppliers")
