"""Production batches, finished-good lots, and recipe outputs

Revision ID: 8d3f1a6c4b20
Revises: d1f3a5c7e9b0
Create Date: 2026-10-19 18:30:00.000000

"""

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


revision = "8d3f1a6c4b20"
down_revision = "d1f3a5c7e9b0"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "ck_inventory_movements_type", "inventory_movements", type_="check"
    )
    op.create_check_constraint(
        "ck_inventory_movements_type",
        "inventory_movements",
        "movement_type IN ('receipt', 'sale_consumption', "
        "'production_consumption', 'production_receipt', 'adjustment', "
        "'return', 'reversal')",
    )

    op.add_column(
        "inventory_items",
        sa.Column("role", sa.String(length=32), nullable=True),
    )
    op.execute(
        "UPDATE inventory_items SET role = 'raw_material' "
        "WHERE item_type IN ('ingredient', 'packaging', 'consumable')"
    )
    op.execute(
        "UPDATE inventory_items SET role = 'general' WHERE role IS NULL"
    )
    op.alter_column("inventory_items", "role", nullable=False)
    op.create_check_constraint(
        "ck_inventory_items_role",
        "inventory_items",
        "role IN ('raw_material', 'finished_good', 'general')",
    )

    op.create_table(
        "recipe_output_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipe_id", sa.Uuid(), nullable=False),
        sa.Column("menu_item_id", sa.Uuid(), nullable=False),
        sa.Column("inventory_item_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.CheckConstraint(
            "quantity > 0", name="ck_recipe_output_lines_quantity_positive"
        ),
        sa.ForeignKeyConstraint(
            ["recipe_id"], ["recipes.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["menu_item_id"], ["menu_items.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["inventory_item_id"], ["inventory_items.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "recipe_id", "menu_item_id", name="uq_recipe_output_lines_menu_item"
        ),
    )
    op.create_index(
        "ix_recipe_output_lines_recipe_id",
        "recipe_output_lines",
        ["recipe_id"],
        unique=False,
    )
    op.create_index(
        "ix_recipe_output_lines_menu_item",
        "recipe_output_lines",
        ["menu_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_recipe_output_lines_inventory_item",
        "recipe_output_lines",
        ["inventory_item_id"],
        unique=False,
    )

    op.create_table(
        "production_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("recipe_id", sa.Uuid(), nullable=True),
        sa.Column("formula_runs", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column(
            "total_material_cost", sa.Numeric(precision=18, scale=2), nullable=True
        ),
        sa.Column("cost_uncertain", sa.Boolean(), nullable=False),
        sa.Column("planned_for", sa.Date(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "notes", sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=True
        ),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("completed_by_id", sa.Uuid(), nullable=True),
        sa.Column("reversed_by_id", sa.Uuid(), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reversal_reason", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'completed', 'cancelled', 'reversed')",
            name="ck_production_batches_status",
        ),
        sa.CheckConstraint(
            "(status IN ('completed', 'reversed')) = (finished_at IS NOT NULL)",
            name="ck_production_batches_finished_at",
        ),
        sa.CheckConstraint(
            "(status IN ('completed', 'reversed')) = (completed_by_id IS NOT NULL)",
            name="ck_production_batches_completed_by",
        ),
        sa.CheckConstraint(
            "(status = 'reversed' AND reversed_at IS NOT NULL "
            "AND reversed_by_id IS NOT NULL AND reversal_reason IS NOT NULL) OR "
            "(status <> 'reversed' AND reversed_at IS NULL "
            "AND reversed_by_id IS NULL AND reversal_reason IS NULL)",
            name="ck_production_batches_reversal_metadata",
        ),
        sa.CheckConstraint(
            "formula_runs IS NULL OR formula_runs > 0",
            name="ck_production_batches_formula_runs_positive",
        ),
        sa.CheckConstraint(
            "(recipe_id IS NULL) = (formula_runs IS NULL)",
            name="ck_production_batches_formula_runs_source",
        ),
        sa.CheckConstraint(
            "total_material_cost IS NULL OR total_material_cost >= 0",
            name="ck_production_batches_total_material_cost",
        ),
        sa.ForeignKeyConstraint(
            ["recipe_id"], ["recipes.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["completed_by_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reversed_by_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number"),
    )
    op.create_index(
        "ix_production_batches_status", "production_batches", ["status"]
    )
    op.create_index(
        "ix_production_batches_planned_for", "production_batches", ["planned_for"]
    )
    op.create_index(
        "ix_production_batches_finished_at", "production_batches", ["finished_at"]
    )
    op.create_index(
        "ix_production_batches_recipe", "production_batches", ["recipe_id"]
    )

    op.create_table(
        "production_batch_ingredient_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Uuid(), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("planned_quantity", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("actual_quantity", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("movement_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "line_no > 0", name="ck_production_batch_ingredient_line_no"
        ),
        sa.CheckConstraint(
            "planned_quantity > 0",
            name="ck_production_batch_ingredient_planned_positive",
        ),
        sa.CheckConstraint(
            "actual_quantity IS NULL OR actual_quantity >= 0",
            name="ck_production_batch_ingredient_actual_nonnegative",
        ),
        sa.CheckConstraint(
            "(actual_quantity IS NULL OR actual_quantity = 0) = (movement_id IS NULL)",
            name="ck_production_batch_ingredient_movement",
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"], ["production_batches.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["inventory_item_id"], ["inventory_items.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["movement_id"], ["inventory_movements.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "batch_id", "line_no", name="uq_production_batch_ingredient_line_no"
        ),
        sa.UniqueConstraint(
            "batch_id",
            "inventory_item_id",
            name="uq_production_batch_ingredient_item",
        ),
    )
    op.create_index(
        "ix_production_batch_ingredient_lines_batch_id",
        "production_batch_ingredient_lines",
        ["batch_id"],
        unique=False,
    )
    op.create_index(
        "ix_production_batch_ingredient_item",
        "production_batch_ingredient_lines",
        ["inventory_item_id"],
        unique=False,
    )

    op.create_table(
        "production_batch_output_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("menu_item_id", sa.Uuid(), nullable=False),
        sa.Column("inventory_item_id", sa.Uuid(), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("planned_quantity", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column(
            "actual_good_quantity", sa.Numeric(precision=18, scale=4), nullable=True
        ),
        sa.Column(
            "waste_quantity",
            sa.Numeric(precision=18, scale=4),
            nullable=False,
        ),
        sa.Column("unit_cost", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("cost_uncertain", sa.Boolean(), nullable=False),
        sa.Column("movement_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "line_no > 0", name="ck_production_batch_output_line_no"
        ),
        sa.CheckConstraint(
            "planned_quantity > 0",
            name="ck_production_batch_output_planned_positive",
        ),
        sa.CheckConstraint(
            "actual_good_quantity IS NULL OR actual_good_quantity >= 0",
            name="ck_production_batch_output_good_nonnegative",
        ),
        sa.CheckConstraint(
            "waste_quantity >= 0",
            name="ck_production_batch_output_waste_nonnegative",
        ),
        sa.CheckConstraint(
            "unit_cost IS NULL OR unit_cost >= 0",
            name="ck_production_batch_output_unit_cost",
        ),
        sa.CheckConstraint(
            "(actual_good_quantity IS NULL OR actual_good_quantity = 0) = "
            "(movement_id IS NULL)",
            name="ck_production_batch_output_movement",
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"], ["production_batches.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["menu_item_id"], ["menu_items.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["inventory_item_id"], ["inventory_items.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["movement_id"], ["inventory_movements.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "batch_id", "line_no", name="uq_production_batch_output_no"
        ),
        sa.UniqueConstraint(
            "batch_id", "menu_item_id", name="uq_production_batch_output_menu_item"
        ),
    )
    op.create_index(
        "ix_production_batch_output_lines_batch_id",
        "production_batch_output_lines",
        ["batch_id"],
        unique=False,
    )
    op.create_index(
        "ix_production_batch_output_inventory_item",
        "production_batch_output_lines",
        ["inventory_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_production_batch_output_menu_item",
        "production_batch_output_lines",
        ["menu_item_id"],
        unique=False,
    )

    op.create_table(
        "finished_good_lots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lot_number", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("origin", sa.String(length=32), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=True),
        sa.Column("output_line_id", sa.Uuid(), nullable=True),
        sa.Column("opening_stock_line_id", sa.Uuid(), nullable=True),
        sa.Column("inventory_item_id", sa.Uuid(), nullable=False),
        sa.Column("produced_quantity", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("quantity_on_hand", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column(
            "reserved_quantity",
            sa.Numeric(precision=18, scale=4),
            nullable=False,
        ),
        sa.Column("unit_cost", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "origin IN ('production', 'opening_stock')",
            name="ck_finished_good_lots_origin",
        ),
        sa.CheckConstraint(
            "(origin = 'production' AND batch_id IS NOT NULL "
            "AND output_line_id IS NOT NULL AND opening_stock_line_id IS NULL) OR "
            "(origin = 'opening_stock' AND batch_id IS NULL "
            "AND output_line_id IS NULL AND opening_stock_line_id IS NOT NULL)",
            name="ck_finished_good_lots_source",
        ),
        sa.CheckConstraint(
            "produced_quantity > 0 AND quantity_on_hand >= 0 "
            "AND reserved_quantity >= 0 AND reserved_quantity <= quantity_on_hand",
            name="ck_finished_good_lots_quantities",
        ),
        sa.CheckConstraint(
            "unit_cost IS NULL OR unit_cost >= 0",
            name="ck_finished_good_lots_unit_cost",
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"], ["production_batches.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["output_line_id"],
            ["production_batch_output_lines.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["opening_stock_line_id"],
            ["stock_adjustment_lines.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["inventory_item_id"], ["inventory_items.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lot_number"),
        sa.UniqueConstraint("output_line_id"),
        sa.UniqueConstraint("opening_stock_line_id"),
    )
    op.create_index(
        "ix_finished_good_lots_inventory_item_id",
        "finished_good_lots",
        ["inventory_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_finished_good_lots_item_finished",
        "finished_good_lots",
        ["inventory_item_id", "finished_at"],
        unique=False,
    )
    op.create_index(
        "ix_finished_good_lots_expiry",
        "finished_good_lots",
        ["expiry_date"],
        unique=False,
    )
    op.create_index(
        "ix_finished_good_lots_batch",
        "finished_good_lots",
        ["batch_id"],
        unique=False,
    )

    op.create_table(
        "finished_good_lot_movements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lot_id", sa.Uuid(), nullable=False),
        sa.Column("movement_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "quantity <> 0", name="ck_finished_good_lot_movement_quantity"
        ),
        sa.ForeignKeyConstraint(
            ["lot_id"], ["finished_good_lots.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["movement_id"], ["inventory_movements.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "lot_id", "movement_id", name="uq_finished_good_lot_movement"
        ),
    )
    op.create_index(
        "ix_finished_good_lot_movements_lot_id",
        "finished_good_lot_movements",
        ["lot_id"],
        unique=False,
    )
    op.create_index(
        "ix_finished_good_lot_movements_movement",
        "finished_good_lot_movements",
        ["movement_id"],
        unique=False,
    )

    op.create_table(
        "finished_good_lot_allocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lot_movement_id", sa.Uuid(), nullable=False),
        sa.Column("order_line_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "quantity > 0", name="ck_finished_good_lot_allocation_quantity"
        ),
        sa.ForeignKeyConstraint(
            ["lot_movement_id"],
            ["finished_good_lot_movements.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["order_line_id"], ["order_lines.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "lot_movement_id",
            "order_line_id",
            name="uq_finished_good_lot_allocation",
        ),
    )
    op.create_index(
        "ix_finished_good_lot_allocations_order_line",
        "finished_good_lot_allocations",
        ["order_line_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_finished_good_lot_allocations_order_line",
        table_name="finished_good_lot_allocations",
    )
    op.drop_table("finished_good_lot_allocations")
    op.drop_index(
        "ix_finished_good_lot_movements_movement",
        table_name="finished_good_lot_movements",
    )
    op.drop_index(
        "ix_finished_good_lot_movements_lot_id",
        table_name="finished_good_lot_movements",
    )
    op.drop_table("finished_good_lot_movements")
    op.drop_index("ix_finished_good_lots_batch", table_name="finished_good_lots")
    op.drop_index("ix_finished_good_lots_expiry", table_name="finished_good_lots")
    op.drop_index(
        "ix_finished_good_lots_item_finished", table_name="finished_good_lots"
    )
    op.drop_index(
        "ix_finished_good_lots_inventory_item_id", table_name="finished_good_lots"
    )
    op.drop_table("finished_good_lots")
    op.drop_index(
        "ix_production_batch_output_menu_item",
        table_name="production_batch_output_lines",
    )
    op.drop_index(
        "ix_production_batch_output_inventory_item",
        table_name="production_batch_output_lines",
    )
    op.drop_index(
        "ix_production_batch_output_lines_batch_id",
        table_name="production_batch_output_lines",
    )
    op.drop_table("production_batch_output_lines")
    op.drop_index(
        "ix_production_batch_ingredient_item",
        table_name="production_batch_ingredient_lines",
    )
    op.drop_index(
        "ix_production_batch_ingredient_lines_batch_id",
        table_name="production_batch_ingredient_lines",
    )
    op.drop_table("production_batch_ingredient_lines")
    op.drop_index("ix_production_batches_recipe", table_name="production_batches")
    op.drop_index("ix_production_batches_finished_at", table_name="production_batches")
    op.drop_index("ix_production_batches_planned_for", table_name="production_batches")
    op.drop_index("ix_production_batches_status", table_name="production_batches")
    op.drop_table("production_batches")
    op.drop_index(
        "ix_recipe_output_lines_inventory_item", table_name="recipe_output_lines"
    )
    op.drop_index(
        "ix_recipe_output_lines_menu_item", table_name="recipe_output_lines"
    )
    op.drop_index("ix_recipe_output_lines_recipe_id", table_name="recipe_output_lines")
    op.drop_table("recipe_output_lines")
    op.drop_constraint(
        "ck_inventory_items_role", "inventory_items", type_="check"
    )
    op.drop_column("inventory_items", "role")
    op.drop_constraint(
        "ck_inventory_movements_type", "inventory_movements", type_="check"
    )
    op.create_check_constraint(
        "ck_inventory_movements_type",
        "inventory_movements",
        "movement_type IN ('receipt', 'sale_consumption', 'adjustment', "
        "'return', 'reversal')",
    )
