"""Persist configurable POS fees and order fee snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "c9f3a5b7d1e2"
down_revision = "b4e6a8c0d2f3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "orders",
        sa.Column(
            "fee_total",
            sa.Numeric(18, 2),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.drop_constraint("ck_orders_amounts_non_negative", "orders", type_="check")
    op.drop_constraint("ck_orders_total", "orders", type_="check")
    op.create_check_constraint(
        "ck_orders_amounts_non_negative",
        "orders",
        "subtotal >= 0 AND discount_total >= 0 AND tax_total >= 0 "
        "AND fee_total >= 0 AND total >= 0",
    )
    op.create_check_constraint(
        "ck_orders_total",
        "orders",
        "total = subtotal - discount_total + fee_total",
    )
    op.create_table(
        "order_fee_types",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(btrim(name)) > 0", name="ck_order_fee_types_name_not_blank"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "order_fees",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("fee_type_id", sa.Uuid(), nullable=False),
        sa.Column("fee_name", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.CheckConstraint(
            "length(btrim(fee_name)) > 0", name="ck_order_fees_name_not_blank"
        ),
        sa.CheckConstraint("amount > 0", name="ck_order_fees_amount_positive"),
        sa.ForeignKeyConstraint(["fee_type_id"], ["order_fee_types.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", "fee_type_id", name="uq_order_fees_order_type"),
    )
    op.create_index("ix_order_fees_order_id", "order_fees", ["order_id"])


def downgrade():
    op.drop_index("ix_order_fees_order_id", table_name="order_fees")
    op.drop_table("order_fees")
    op.drop_table("order_fee_types")
    op.drop_constraint("ck_orders_total", "orders", type_="check")
    op.drop_constraint("ck_orders_amounts_non_negative", "orders", type_="check")
    op.drop_column("orders", "fee_total")
    op.create_check_constraint(
        "ck_orders_amounts_non_negative",
        "orders",
        "subtotal >= 0 AND discount_total >= 0 AND tax_total >= 0 AND total >= 0",
    )
    op.create_check_constraint(
        "ck_orders_total", "orders", "total = subtotal - discount_total"
    )
