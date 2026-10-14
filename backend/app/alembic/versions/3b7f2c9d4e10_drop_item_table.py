"""Drop template item table

Revision ID: 3b7f2c9d4e10
Revises: fe56fa70289e
Create Date: 2026-10-14 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '3b7f2c9d4e10'
down_revision = 'fe56fa70289e'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('item')


def downgrade():
    op.create_table(
        'item',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('owner_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['user.id'], name='item_owner_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
