"""Report query indexes

Revision ID: d1f3a5c7e9b0
Revises: c0e2a4b6d8f1
Create Date: 2026-10-15 15:20:00.000000

"""

from alembic import op

revision = "d1f3a5c7e9b0"
down_revision = "c0e2a4b6d8f1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_orders_completed_at", "orders", ["completed_at"])
    op.create_index(
        "ix_inventory_movements_item_occurred",
        "inventory_movements",
        ["item_id", "occurred_at"],
    )


def downgrade():
    op.drop_index("ix_inventory_movements_item_occurred", table_name="inventory_movements")
    op.drop_index("ix_orders_completed_at", table_name="orders")
