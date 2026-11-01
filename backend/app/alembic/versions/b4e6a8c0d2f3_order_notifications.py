"""Add persistent owner notifications for completed orders."""

import sqlalchemy as sa
from alembic import op

revision = "b4e6a8c0d2f3"
down_revision = "a2d4f6b8c0e1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_id", "order_id", name="uq_notifications_owner_order"
        ),
    )
    op.create_index(
        "ix_notifications_owner_created",
        "notifications",
        ["owner_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_owner_read",
        "notifications",
        ["owner_id", "read_at"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_notifications_owner_read", table_name="notifications")
    op.drop_index("ix_notifications_owner_created", table_name="notifications")
    op.drop_table("notifications")
