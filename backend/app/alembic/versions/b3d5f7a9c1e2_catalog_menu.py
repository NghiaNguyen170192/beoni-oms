"""Catalog menu: menu categories (seeded) and menu items

Revision ID: b3d5f7a9c1e2
Revises: a7c4e1f2b9d0
Create Date: 2026-10-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'b3d5f7a9c1e2'
down_revision = 'a7c4e1f2b9d0'
branch_labels = None
depends_on = None

SEED_CATEGORIES = ("Cà phê", "Trà", "Đồ ăn", "Khác")


def upgrade():
    op.create_table(
        'menu_categories',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'uq_menu_categories_active_name',
        'menu_categories',
        [sa.text('lower(name)')],
        unique=True,
        postgresql_where=sa.text('is_active'),
    )
    categories = sa.table(
        'menu_categories',
        sa.column('id', sa.Uuid()),
        sa.column('name', sa.String()),
        sa.column('sort_order', sa.Integer()),
        sa.column('is_active', sa.Boolean()),
        sa.column('created_at', sa.DateTime(timezone=True)),
        sa.column('updated_at', sa.DateTime(timezone=True)),
    )
    for position, name in enumerate(SEED_CATEGORIES):
        op.execute(
            categories.insert().values(
                id=sa.func.gen_random_uuid(),
                name=name,
                sort_order=position,
                is_active=True,
                created_at=sa.func.now(),
                updated_at=sa.func.now(),
            )
        )

    op.create_table(
        'menu_items',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('code', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=True),
        sa.Column('category_id', sa.Uuid(), nullable=False),
        sa.Column('price', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('product_type', sa.String(length=32), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_available', sa.Boolean(), nullable=False),
        sa.Column('image_path', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('price >= 0', name='ck_menu_items_price_non_negative'),
        sa.CheckConstraint(
            "product_type IN ('prepared', 'direct_sale', 'non_stock')",
            name='ck_menu_items_product_type',
        ),
        sa.ForeignKeyConstraint(['category_id'], ['menu_categories.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_menu_items_category_id', 'menu_items', ['category_id'], unique=False)
    op.create_index('uq_menu_items_code', 'menu_items', ['code'], unique=True)


def downgrade():
    op.drop_index('uq_menu_items_code', table_name='menu_items')
    op.drop_index('ix_menu_items_category_id', table_name='menu_items')
    op.drop_table('menu_items')
    op.drop_index('uq_menu_categories_active_name', table_name='menu_categories')
    op.drop_table('menu_categories')
