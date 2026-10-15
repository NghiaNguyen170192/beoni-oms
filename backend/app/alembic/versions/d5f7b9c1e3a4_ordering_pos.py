"""Ordering POS: orders, order lines (RESTRICT to menu items), daily order numbers, tax rate setting

Revision ID: d5f7b9c1e3a4
Revises: c4e6a8b0d2f3
Create Date: 2026-10-15 01:46:25.765543

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'd5f7b9c1e3a4'
down_revision = 'c4e6a8b0d2f3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('order_number_counters',
    sa.Column('business_date', sa.Date(), nullable=False),
    sa.Column('last_number', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('business_date')
    )
    op.create_table('orders',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('number', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
    sa.Column('business_date', sa.Date(), nullable=False),
    sa.Column('order_type', sa.String(length=32), nullable=False),
    sa.Column('table_label', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True),
    sa.Column('notes', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('tax_rate', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('subtotal', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('discount_total', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('order_discount_type', sa.String(length=16), nullable=True),
    sa.Column('order_discount_value', sa.Numeric(precision=18, scale=2), nullable=True),
    sa.Column('order_discount_amount', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('order_discount_by_id', sa.Uuid(), nullable=True),
    sa.Column('tax_total', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('total', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('cashier_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_by_id', sa.Uuid(), nullable=True),
    sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cancelled_by_id', sa.Uuid(), nullable=True),
    sa.Column('cancel_reason', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    sa.CheckConstraint("(status = 'cancelled') = (cancelled_at IS NOT NULL)", name='ck_orders_cancelled_at'),
    sa.CheckConstraint("order_discount_type IS NULL OR order_discount_type IN ('amount', 'percent')", name='ck_orders_discount_type'),
    sa.CheckConstraint("order_type = 'dine_in' OR table_label IS NULL", name='ck_orders_table_label'),
    sa.CheckConstraint("order_type IN ('counter', 'takeaway', 'dine_in')", name='ck_orders_type'),
    sa.CheckConstraint("status <> 'cancelled' OR cancel_reason IS NOT NULL", name='ck_orders_cancel_reason'),
    sa.CheckConstraint("status IN ('draft', 'confirmed', 'paid', 'completed', 'cancelled', 'partially_refunded', 'refunded')", name='ck_orders_status'),
    sa.CheckConstraint("status NOT IN ('completed', 'partially_refunded', 'refunded') OR completed_at IS NOT NULL", name='ck_orders_completed_at'),
    sa.CheckConstraint('subtotal >= 0 AND discount_total >= 0 AND tax_total >= 0 AND total >= 0', name='ck_orders_amounts_non_negative'),
    sa.CheckConstraint('tax_rate >= 0 AND tax_rate <= 100', name='ck_orders_tax_rate'),
    sa.CheckConstraint('total = subtotal - discount_total', name='ck_orders_total'),
    sa.ForeignKeyConstraint(['cancelled_by_id'], ['user.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['cashier_id'], ['user.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['completed_by_id'], ['user.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['order_discount_by_id'], ['user.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_orders_business_date', 'orders', ['business_date'], unique=False)
    op.create_index('ix_orders_cashier_created', 'orders', ['cashier_id', 'created_at'], unique=False)
    op.create_index('ix_orders_status', 'orders', ['status'], unique=False)
    op.create_index('uq_orders_number', 'orders', ['number'], unique=True)
    op.create_table('order_lines',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('order_id', sa.Uuid(), nullable=False),
    sa.Column('line_no', sa.Integer(), nullable=False),
    sa.Column('menu_item_id', sa.Uuid(), nullable=False),
    sa.Column('item_code', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
    sa.Column('item_name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('product_type', sa.String(length=32), nullable=False),
    sa.Column('unit_price', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('quantity', sa.Numeric(precision=18, scale=4), nullable=False),
    sa.Column('note', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    sa.Column('discount_type', sa.String(length=16), nullable=True),
    sa.Column('discount_value', sa.Numeric(precision=18, scale=2), nullable=True),
    sa.Column('discount_amount', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('discount_by_id', sa.Uuid(), nullable=True),
    sa.Column('line_total', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('order_discount_share', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('net_total', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('tax_rate', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('tax_amount', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("discount_type IS NULL OR discount_type IN ('amount', 'percent')", name='ck_order_lines_discount_type'),
    sa.CheckConstraint("product_type IN ('prepared', 'direct_sale', 'non_stock')", name='ck_order_lines_product_type'),
    sa.CheckConstraint('discount_amount >= 0 AND line_total >= 0 AND net_total >= 0 AND order_discount_share >= 0 AND tax_amount >= 0', name='ck_order_lines_amounts_non_negative'),
    sa.CheckConstraint('net_total = line_total - order_discount_share', name='ck_order_lines_net'),
    sa.CheckConstraint('quantity > 0 AND quantity = round(quantity, 3)', name='ck_order_lines_quantity'),
    sa.CheckConstraint('unit_price >= 0', name='ck_order_lines_unit_price'),
    sa.ForeignKeyConstraint(['discount_by_id'], ['user.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['menu_item_id'], ['menu_items.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_order_lines_menu_item_id', 'order_lines', ['menu_item_id'], unique=False)
    op.create_index('ix_order_lines_order_id', 'order_lines', ['order_id'], unique=False)
    op.add_column(
        'business_settings',
        sa.Column('tax_rate', sa.Numeric(precision=5, scale=2), server_default='0', nullable=False),
    )
    op.alter_column('business_settings', 'tax_rate', server_default=None)
    op.create_check_constraint(
        'ck_business_settings_tax_rate', 'business_settings', 'tax_rate >= 0 AND tax_rate <= 100'
    )


def downgrade():
    op.drop_constraint('ck_business_settings_tax_rate', 'business_settings', type_='check')
    op.drop_column('business_settings', 'tax_rate')
    op.drop_index('ix_order_lines_order_id', table_name='order_lines')
    op.drop_index('ix_order_lines_menu_item_id', table_name='order_lines')
    op.drop_table('order_lines')
    op.drop_index('uq_orders_number', table_name='orders')
    op.drop_index('ix_orders_status', table_name='orders')
    op.drop_index('ix_orders_cashier_created', table_name='orders')
    op.drop_index('ix_orders_business_date', table_name='orders')
    op.drop_table('orders')
    op.drop_table('order_number_counters')
