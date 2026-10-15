"""Inventory core: items, balances, append-only movement ledger, stock adjustments

Revision ID: c4e6a8b0d2f3
Revises: b3d5f7a9c1e2
Create Date: 2026-10-15 01:39:07.407783

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'c4e6a8b0d2f3'
down_revision = 'b3d5f7a9c1e2'
branch_labels = None
depends_on = None

SEED_CATEGORIES = ("Nguyên vật liệu", "Công cụ dụng cụ", "Hàng bán sẵn", "Bao bì")


def upgrade():
    op.create_table('inventory_categories',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('inventory_items',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('sku', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=True),
    sa.Column('category_id', sa.Uuid(), nullable=False),
    sa.Column('item_type', sa.String(length=32), nullable=False),
    sa.Column('base_unit', sa.String(length=16), nullable=False),
    sa.Column('purchase_unit', sa.String(length=16), nullable=False),
    sa.Column('conversion_factor', sa.Numeric(precision=18, scale=4), nullable=False),
    sa.Column('min_stock', sa.Numeric(precision=18, scale=4), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('barcode', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("base_unit IN ('g', 'kg', 'ml', 'l', 'piece', 'pack', 'bottle', 'cup', 'box')", name='ck_inventory_items_base_unit'),
    sa.CheckConstraint("item_type IN ('ingredient', 'merchandise', 'packaging', 'consumable')", name='ck_inventory_items_type'),
    sa.CheckConstraint("purchase_unit IN ('g', 'kg', 'ml', 'l', 'piece', 'pack', 'bottle', 'cup', 'box')", name='ck_inventory_items_purchase_unit'),
    sa.CheckConstraint('conversion_factor > 0', name='ck_inventory_items_conversion_positive'),
    sa.CheckConstraint('min_stock >= 0', name='ck_inventory_items_min_stock'),
    sa.CheckConstraint('purchase_unit <> base_unit OR conversion_factor = 1', name='ck_inventory_items_same_unit_factor_one'),
    sa.ForeignKeyConstraint(['category_id'], ['inventory_categories.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inventory_items_category_id'), 'inventory_items', ['category_id'], unique=False)
    op.create_index('uq_inventory_items_barcode', 'inventory_items', ['barcode'], unique=True)
    op.create_index('uq_inventory_items_sku', 'inventory_items', ['sku'], unique=True)
    op.create_table('stock_adjustments',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('number', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('note', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
    sa.Column('posted_by_id', sa.Uuid(), nullable=False),
    sa.Column('posted_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('reversed_by_id', sa.Uuid(), nullable=True),
    sa.Column('reversed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('reversal_note', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
    sa.CheckConstraint("(status = 'reversed') = (reversed_at IS NOT NULL)", name='ck_stock_adjustments_reversed_at'),
    sa.CheckConstraint("status IN ('posted', 'reversed')", name='ck_stock_adjustments_status'),
    sa.ForeignKeyConstraint(['posted_by_id'], ['user.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['reversed_by_id'], ['user.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('number')
    )
    op.create_table('inventory_balances',
    sa.Column('item_id', sa.Uuid(), nullable=False),
    sa.Column('quantity', sa.Numeric(precision=18, scale=4), nullable=False),
    sa.Column('avg_unit_cost', sa.Numeric(precision=18, scale=4), nullable=False),
    sa.Column('value', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('avg_unit_cost >= 0', name='ck_inventory_balances_avg_cost'),
    sa.ForeignKeyConstraint(['item_id'], ['inventory_items.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('item_id')
    )
    op.create_table('inventory_movements',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('seq', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('item_id', sa.Uuid(), nullable=False),
    sa.Column('movement_type', sa.String(length=32), nullable=False),
    sa.Column('quantity', sa.Numeric(precision=18, scale=4), nullable=False),
    sa.Column('unit_cost', sa.Numeric(precision=18, scale=4), nullable=False),
    sa.Column('value', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('quantity_after', sa.Numeric(precision=18, scale=4), nullable=False),
    sa.Column('cost_uncertain', sa.Boolean(), nullable=False),
    sa.Column('source_type', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('source_id', sa.Uuid(), nullable=False),
    sa.Column('actor_id', sa.Uuid(), nullable=True),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("movement_type IN ('receipt', 'sale_consumption', 'adjustment', 'return', 'reversal')", name='ck_inventory_movements_type'),
    sa.CheckConstraint('quantity <> 0', name='ck_inventory_movements_quantity_nonzero'),
    sa.CheckConstraint('unit_cost >= 0', name='ck_inventory_movements_unit_cost'),
    sa.ForeignKeyConstraint(['actor_id'], ['user.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['item_id'], ['inventory_items.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('seq')
    )
    op.create_index('ix_inventory_movements_item_seq', 'inventory_movements', ['item_id', 'seq'], unique=False)
    op.create_index('ix_inventory_movements_occurred_at', 'inventory_movements', ['occurred_at'], unique=False)
    op.create_index('ix_inventory_movements_source', 'inventory_movements', ['source_type', 'source_id'], unique=False)
    op.create_table('stock_adjustment_lines',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('adjustment_id', sa.Uuid(), nullable=False),
    sa.Column('line_no', sa.Integer(), nullable=False),
    sa.Column('item_id', sa.Uuid(), nullable=False),
    sa.Column('reason', sa.String(length=32), nullable=False),
    sa.Column('counted_quantity', sa.Numeric(precision=18, scale=4), nullable=True),
    sa.Column('previous_quantity', sa.Numeric(precision=18, scale=4), nullable=False),
    sa.Column('quantity_change', sa.Numeric(precision=18, scale=4), nullable=False),
    sa.Column('resulting_quantity', sa.Numeric(precision=18, scale=4), nullable=False),
    sa.Column('unit_cost', sa.Numeric(precision=18, scale=4), nullable=False),
    sa.Column('movement_id', sa.Uuid(), nullable=True),
    sa.CheckConstraint("(reason = 'physical_count') = (counted_quantity IS NOT NULL)", name='ck_stock_adjustment_lines_counted'),
    sa.CheckConstraint("reason IN ('physical_count', 'spoilage', 'expired', 'damaged', 'missing', 'correction')", name='ck_stock_adjustment_lines_reason'),
    sa.CheckConstraint('(quantity_change = 0) = (movement_id IS NULL)', name='ck_stock_adjustment_lines_movement'),
    sa.CheckConstraint('resulting_quantity = previous_quantity + quantity_change', name='ck_stock_adjustment_lines_result'),
    sa.ForeignKeyConstraint(['adjustment_id'], ['stock_adjustments.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['item_id'], ['inventory_items.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['movement_id'], ['inventory_movements.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_stock_adjustment_lines_adjustment_id'), 'stock_adjustment_lines', ['adjustment_id'], unique=False)
    op.create_index(op.f('ix_stock_adjustment_lines_item_id'), 'stock_adjustment_lines', ['item_id'], unique=False)

    op.execute(
        """
        CREATE FUNCTION inventory_movements_reject_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'inventory_movements is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER inventory_movements_append_only
        BEFORE UPDATE OR DELETE ON inventory_movements
        FOR EACH ROW EXECUTE FUNCTION inventory_movements_reject_mutation()
        """
    )

    categories = sa.table(
        'inventory_categories',
        sa.column('id', sa.Uuid()),
        sa.column('name', sa.String()),
        sa.column('sort_order', sa.Integer()),
        sa.column('is_active', sa.Boolean()),
    )
    for position, name in enumerate(SEED_CATEGORIES):
        op.execute(
            categories.insert().values(
                id=sa.func.gen_random_uuid(),
                name=name,
                sort_order=position,
                is_active=True,
            )
        )


def downgrade():
    op.drop_index(op.f('ix_stock_adjustment_lines_item_id'), table_name='stock_adjustment_lines')
    op.drop_index(op.f('ix_stock_adjustment_lines_adjustment_id'), table_name='stock_adjustment_lines')
    op.drop_table('stock_adjustment_lines')
    op.execute("DROP TRIGGER inventory_movements_append_only ON inventory_movements")
    op.execute("DROP FUNCTION inventory_movements_reject_mutation()")
    op.drop_index('ix_inventory_movements_source', table_name='inventory_movements')
    op.drop_index('ix_inventory_movements_occurred_at', table_name='inventory_movements')
    op.drop_index('ix_inventory_movements_item_seq', table_name='inventory_movements')
    op.drop_table('inventory_movements')
    op.drop_table('inventory_balances')
    op.drop_table('stock_adjustments')
    op.drop_index('uq_inventory_items_sku', table_name='inventory_items')
    op.drop_index('uq_inventory_items_barcode', table_name='inventory_items')
    op.drop_index(op.f('ix_inventory_items_category_id'), table_name='inventory_items')
    op.drop_table('inventory_items')
    op.drop_table('inventory_categories')
