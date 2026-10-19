"""Add reusable production batch templates

Revision ID: a2d4f6b8c0e1
Revises: c2a4e6f8b0d1
Create Date: 2026-10-19 23:45:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "a2d4f6b8c0e1"
down_revision = "c2a4e6f8b0d1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "production_batch_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("recipe_id", sa.Uuid(), nullable=True),
        sa.Column("formula_runs", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "formula_runs IS NULL OR formula_runs > 0",
            name="ck_production_batch_templates_formula_runs_positive",
        ),
        sa.CheckConstraint(
            "(recipe_id IS NULL) = (formula_runs IS NULL)",
            name="ck_production_batch_templates_formula_runs_source",
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_production_batch_templates_name",
        "production_batch_templates",
        ["name"],
        unique=False,
    )

    op.create_table(
        "production_batch_template_ingredient_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Uuid(), nullable=False),
        sa.Column(
            "planned_quantity", sa.Numeric(precision=18, scale=4), nullable=False
        ),
        sa.CheckConstraint(
            "line_no > 0", name="ck_production_template_ingredient_line_no"
        ),
        sa.CheckConstraint(
            "planned_quantity > 0",
            name="ck_production_template_ingredient_planned_positive",
        ),
        sa.ForeignKeyConstraint(
            ["inventory_item_id"], ["inventory_items.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["template_id"], ["production_batch_templates.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "template_id",
            "line_no",
            name="uq_production_template_ingredient_line_no",
        ),
        sa.UniqueConstraint(
            "template_id",
            "inventory_item_id",
            name="uq_production_template_ingredient_item",
        ),
    )
    op.create_index(
        "ix_production_batch_template_ingredient_lines_template_id",
        "production_batch_template_ingredient_lines",
        ["template_id"],
        unique=False,
    )
    op.create_index(
        "ix_production_template_ingredient_item",
        "production_batch_template_ingredient_lines",
        ["inventory_item_id"],
        unique=False,
    )

    op.create_table(
        "production_batch_template_output_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("menu_item_id", sa.Uuid(), nullable=False),
        sa.Column("inventory_item_id", sa.Uuid(), nullable=False),
        sa.Column(
            "planned_quantity", sa.Numeric(precision=18, scale=4), nullable=False
        ),
        sa.CheckConstraint("line_no > 0", name="ck_production_template_output_line_no"),
        sa.CheckConstraint(
            "planned_quantity > 0",
            name="ck_production_template_output_planned_positive",
        ),
        sa.ForeignKeyConstraint(
            ["inventory_item_id"], ["inventory_items.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["menu_item_id"], ["menu_items.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["template_id"], ["production_batch_templates.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "template_id", "line_no", name="uq_production_template_output_line_no"
        ),
        sa.UniqueConstraint(
            "template_id",
            "menu_item_id",
            name="uq_production_template_output_menu",
        ),
    )
    op.create_index(
        "ix_production_batch_template_output_lines_template_id",
        "production_batch_template_output_lines",
        ["template_id"],
        unique=False,
    )
    op.create_index(
        "ix_production_template_output_menu",
        "production_batch_template_output_lines",
        ["menu_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_production_template_output_inventory",
        "production_batch_template_output_lines",
        ["inventory_item_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_production_template_output_inventory",
        table_name="production_batch_template_output_lines",
    )
    op.drop_index(
        "ix_production_template_output_menu",
        table_name="production_batch_template_output_lines",
    )
    op.drop_index(
        "ix_production_batch_template_output_lines_template_id",
        table_name="production_batch_template_output_lines",
    )
    op.drop_table("production_batch_template_output_lines")
    op.drop_index(
        "ix_production_template_ingredient_item",
        table_name="production_batch_template_ingredient_lines",
    )
    op.drop_index(
        "ix_production_batch_template_ingredient_lines_template_id",
        table_name="production_batch_template_ingredient_lines",
    )
    op.drop_table("production_batch_template_ingredient_lines")
    op.drop_index(
        "ix_production_batch_templates_name", table_name="production_batch_templates"
    )
    op.drop_table("production_batch_templates")
