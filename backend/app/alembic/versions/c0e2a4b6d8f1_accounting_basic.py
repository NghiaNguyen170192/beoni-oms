"""Money accounts, expenses, and supplier payments

Revision ID: c0e2a4b6d8f1
Revises: b9d1f3a5c7e8
Create Date: 2026-10-15 14:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "c0e2a4b6d8f1"
down_revision = "b9d1f3a5c7e8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "money_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('cash', 'bank')", name="ck_money_accounts_kind"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_money_accounts_name"),
    )
    op.execute(
        """
        INSERT INTO money_accounts (id, name, kind, is_active, created_at) VALUES
            (gen_random_uuid(), 'Cash drawer', 'cash', true, now()),
            (gen_random_uuid(), 'Bank', 'bank', true, now())
        """
    )
    op.add_column("payment_methods", sa.Column("account_id", sa.Uuid(), nullable=True))
    op.execute(
        """
        UPDATE payment_methods AS method
        SET account_id = account.id
        FROM money_accounts AS account
        WHERE account.name = CASE WHEN method.kind = 'cash' THEN 'Cash drawer' ELSE 'Bank' END
        """
    )
    op.alter_column("payment_methods", "account_id", nullable=False)
    op.create_foreign_key(
        "fk_payment_methods_account_id",
        "payment_methods",
        "money_accounts",
        ["account_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_table(
        "cash_movements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.CheckConstraint("amount <> 0", name="ck_cash_movements_amount"),
        sa.ForeignKeyConstraint(["account_id"], ["money_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_type", "source_id", name="uq_cash_movements_source"),
    )
    op.create_index(
        "ix_cash_movements_account_time",
        "cash_movements",
        ["account_id", "occurred_at"],
    )
    op.execute(
        """
        INSERT INTO cash_movements
            (id, account_id, amount, occurred_at, source_type, source_id, actor_id)
        SELECT gen_random_uuid(), method.account_id, payment.amount,
               payment.recorded_at, 'payment', payment.id, payment.recorded_by_id
        FROM payments AS payment
        JOIN payment_methods AS method ON method.id = payment.method_id
        """
    )
    op.execute(
        """
        INSERT INTO cash_movements
            (id, account_id, amount, occurred_at, source_type, source_id, actor_id, note)
        SELECT gen_random_uuid(), method.account_id, -payment.amount,
               payment.voided_at, 'payment_void', payment.id, payment.voided_by_id,
               payment.void_reason
        FROM payments AS payment
        JOIN payment_methods AS method ON method.id = payment.method_id
        WHERE payment.status = 'voided'
        """
    )
    op.execute(
        """
        INSERT INTO cash_movements
            (id, account_id, amount, occurred_at, source_type, source_id, actor_id)
        SELECT gen_random_uuid(), method.account_id, -refund.amount,
               refund.recorded_at, 'refund', refund.id, refund.recorded_by_id
        FROM refunds AS refund
        JOIN payment_methods AS method ON method.id = refund.method_id
        """
    )
    op.create_table(
        "cash_adjustments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reversal_of_id", sa.Uuid(), nullable=True),
        sa.Column("recorded_by_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount <> 0", name="ck_cash_adjustments_amount"),
        sa.CheckConstraint(
            "status IN ('recorded', 'reversed')", name="ck_cash_adjustments_status"
        ),
        sa.ForeignKeyConstraint(["account_id"], ["money_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["reversal_of_id"], ["cash_adjustments.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "expense_categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_expense_categories_name"),
    )
    op.execute(
        """
        INSERT INTO expense_categories (id, name, is_active, created_at)
        SELECT gen_random_uuid(), name, true, now()
        FROM (VALUES ('Rent'), ('Utilities'), ('Salaries'), ('Equipment'),
                     ('Maintenance'), ('Marketing'), ('Delivery'), ('Other')) AS seed(name)
        """
    )
    op.create_table(
        "expenses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("payment_status", sa.String(length=16), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reversal_reason", sa.String(length=255), nullable=True),
        sa.Column("recorded_by_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_expenses_amount"),
        sa.CheckConstraint(
            "payment_status IN ('paid', 'unpaid')", name="ck_expenses_payment_status"
        ),
        sa.CheckConstraint("status IN ('recorded', 'reversed')", name="ck_expenses_status"),
        sa.CheckConstraint(
            "(payment_status = 'paid') = (account_id IS NOT NULL AND paid_at IS NOT NULL)",
            name="ck_expenses_paid",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["money_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["category_id"], ["expense_categories.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expenses_date", "expenses", ["expense_date"])
    op.create_table(
        "supplier_payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reversal_reason", sa.String(length=255), nullable=True),
        sa.Column("recorded_by_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_supplier_payments_amount"),
        sa.CheckConstraint(
            "status IN ('recorded', 'reversed')", name="ck_supplier_payments_status"
        ),
        sa.ForeignKeyConstraint(["account_id"], ["money_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_supplier_payments_supplier", "supplier_payments", ["supplier_id"])
    op.create_table(
        "supplier_payment_allocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("payable_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_supplier_payment_allocations_amount"),
        sa.ForeignKeyConstraint(["payable_id"], ["supplier_payables.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["payment_id"], ["supplier_payments.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "payment_id", "payable_id", name="uq_supplier_payment_allocations"
        ),
    )


def downgrade():
    op.drop_table("supplier_payment_allocations")
    op.drop_index("ix_supplier_payments_supplier", table_name="supplier_payments")
    op.drop_table("supplier_payments")
    op.drop_index("ix_expenses_date", table_name="expenses")
    op.drop_table("expenses")
    op.drop_table("expense_categories")
    op.drop_table("cash_adjustments")
    op.drop_index("ix_cash_movements_account_time", table_name="cash_movements")
    op.drop_table("cash_movements")
    op.drop_constraint("fk_payment_methods_account_id", "payment_methods", type_="foreignkey")
    op.drop_column("payment_methods", "account_id")
    op.drop_table("money_accounts")
