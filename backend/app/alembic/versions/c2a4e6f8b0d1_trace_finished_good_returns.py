"""Trace finished-good returns to their source lots.

Revision ID: c2a4e6f8b0d1
Revises: 8d3f1a6c4b20
Create Date: 2026-10-19 20:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "c2a4e6f8b0d1"
down_revision = "8d3f1a6c4b20"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "stock_return_lines",
        "unit_cost",
        existing_type=sa.Numeric(precision=18, scale=4),
        nullable=True,
    )
    op.add_column(
        "stock_return_lines",
        sa.Column("finished_good_lot_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "stock_return_lines",
        sa.Column("finished_good_lot_allocation_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_stock_return_lines_finished_good_lot",
        "stock_return_lines",
        "finished_good_lots",
        ["finished_good_lot_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_stock_return_lines_finished_good_allocation",
        "stock_return_lines",
        "finished_good_lot_allocations",
        ["finished_good_lot_allocation_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_stock_return_lines_finished_good_lot",
        "stock_return_lines",
        "(finished_good_lot_id IS NULL) = "
        "(finished_good_lot_allocation_id IS NULL)",
    )
    op.create_index(
        "ix_stock_return_lines_finished_good_allocation",
        "stock_return_lines",
        ["finished_good_lot_allocation_id"],
        unique=False,
    )


def downgrade():
    op.execute(
        "DO $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM stock_return_lines WHERE unit_cost IS NULL) "
        "THEN RAISE EXCEPTION 'Cannot downgrade: finished-good returns have no unit cost'; "
        "END IF; END $$"
    )
    op.drop_index(
        "ix_stock_return_lines_finished_good_allocation",
        table_name="stock_return_lines",
    )
    op.drop_constraint(
        "ck_stock_return_lines_finished_good_lot",
        "stock_return_lines",
        type_="check",
    )
    op.drop_constraint(
        "fk_stock_return_lines_finished_good_allocation",
        "stock_return_lines",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_stock_return_lines_finished_good_lot",
        "stock_return_lines",
        type_="foreignkey",
    )
    op.drop_column("stock_return_lines", "finished_good_lot_allocation_id")
    op.drop_column("stock_return_lines", "finished_good_lot_id")
    op.alter_column(
        "stock_return_lines",
        "unit_cost",
        existing_type=sa.Numeric(precision=18, scale=4),
        nullable=False,
    )
