"""One reversal per cash adjustment.

Revision ID: e2b4d6f8a0c1
Revises: c9f3a5b7d1e2
Create Date: 2026-11-03 09:50:00.000000

"""

from alembic import op

revision = "e2b4d6f8a0c1"
down_revision = "c9f3a5b7d1e2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        "uq_cash_adjustments_reversal_of_id",
        "cash_adjustments",
        ["reversal_of_id"],
    )


def downgrade():
    op.drop_constraint(
        "uq_cash_adjustments_reversal_of_id",
        "cash_adjustments",
        type_="unique",
    )
