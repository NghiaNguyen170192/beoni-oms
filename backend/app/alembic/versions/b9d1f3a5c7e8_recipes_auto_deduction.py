"""Recipes, sale consumption, and stock returns

Revision ID: b9d1f3a5c7e8
Revises: a8c0e2f4b6d7
Create Date: 2026-10-15 13:40:00.000000

"""

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

revision = "b9d1f3a5c7e8"
down_revision = "a8c0e2f4b6d7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "recipes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("menu_item_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_recipes_version_positive"),
        sa.CheckConstraint(
            "kind IN ('recipe', 'stock_link')", name="ck_recipes_kind"
        ),
        sa.ForeignKeyConstraint(
            ["menu_item_id"], ["menu_items.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "menu_item_id", "version", name="uq_recipes_item_version"
        ),
        sa.UniqueConstraint(
            "menu_item_id", "effective_from", name="uq_recipes_item_effective"
        ),
    )
    op.create_index("ix_recipes_menu_item_id", "recipes", ["menu_item_id"])
    op.create_index(
        "ix_recipes_item_effective", "recipes", ["menu_item_id", "effective_from"]
    )
    op.create_table(
        "recipe_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipe_id", sa.Uuid(), nullable=False),
        sa.Column("inventory_item_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.CheckConstraint(
            "quantity > 0", name="ck_recipe_lines_quantity_positive"
        ),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["inventory_item_id"], ["inventory_items.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "recipe_id", "inventory_item_id", name="uq_recipe_lines_item"
        ),
    )
    op.create_index("ix_recipe_lines_recipe_id", "recipe_lines", ["recipe_id"])
    op.add_column(
        "order_lines",
        sa.Column("recipe_version_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "order_lines",
        sa.Column("cogs_amount", sa.Numeric(precision=18, scale=2), nullable=True),
    )
    op.add_column(
        "order_lines",
        sa.Column(
            "cost_uncertain",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_foreign_key(
        "fk_order_lines_recipe_version_id",
        "order_lines",
        "recipes",
        ["recipe_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_order_lines_cogs_non_negative",
        "order_lines",
        "cogs_amount IS NULL OR cogs_amount >= 0",
    )
    op.create_table(
        "movement_allocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("movement_id", sa.Uuid(), nullable=False),
        sa.Column("order_line_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("value", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.CheckConstraint(
            "quantity <> 0", name="ck_movement_allocations_quantity_nonzero"
        ),
        sa.ForeignKeyConstraint(
            ["movement_id"], ["inventory_movements.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["order_line_id"], ["order_lines.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "movement_id", "order_line_id", name="uq_movement_allocations_line"
        ),
    )
    op.create_index(
        "ix_movement_allocations_order_line",
        "movement_allocations",
        ["order_line_id"],
    )
    op.create_table(
        "stock_returns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_returns_order", "stock_returns", ["order_id"])
    op.create_table(
        "stock_return_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("stock_return_id", sa.Uuid(), nullable=False),
        sa.Column("order_line_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("sellable", sa.Boolean(), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("movement_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("quantity > 0", name="ck_stock_return_lines_quantity"),
        sa.CheckConstraint(
            "(sellable AND movement_id IS NOT NULL) OR "
            "(NOT sellable AND movement_id IS NULL)",
            name="ck_stock_return_lines_movement",
        ),
        sa.ForeignKeyConstraint(
            ["stock_return_id"], ["stock_returns.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["order_line_id"], ["order_lines.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["movement_id"], ["inventory_movements.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_stock_return_lines_stock_return_id",
        "stock_return_lines",
        ["stock_return_id"],
    )
    op.create_index(
        "ix_stock_return_lines_order_line",
        "stock_return_lines",
        ["order_line_id"],
    )


def downgrade():
    op.drop_index(
        "ix_stock_return_lines_order_line", table_name="stock_return_lines"
    )
    op.drop_index(
        "ix_stock_return_lines_stock_return_id", table_name="stock_return_lines"
    )
    op.drop_table("stock_return_lines")
    op.drop_index("ix_stock_returns_order", table_name="stock_returns")
    op.drop_table("stock_returns")
    op.drop_index(
        "ix_movement_allocations_order_line", table_name="movement_allocations"
    )
    op.drop_table("movement_allocations")
    op.drop_constraint(
        "ck_order_lines_cogs_non_negative", "order_lines", type_="check"
    )
    op.drop_constraint(
        "fk_order_lines_recipe_version_id", "order_lines", type_="foreignkey"
    )
    op.drop_column("order_lines", "cost_uncertain")
    op.drop_column("order_lines", "cogs_amount")
    op.drop_column("order_lines", "recipe_version_id")
    op.drop_index("ix_recipe_lines_recipe_id", table_name="recipe_lines")
    op.drop_table("recipe_lines")
    op.drop_index("ix_recipes_item_effective", table_name="recipes")
    op.drop_index("ix_recipes_menu_item_id", table_name="recipes")
    op.drop_table("recipes")
