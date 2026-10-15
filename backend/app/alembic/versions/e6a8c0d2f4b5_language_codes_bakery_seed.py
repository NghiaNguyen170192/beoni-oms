"""Interface language, system-assigned item codes, bakery starter catalog

Revision ID: e6a8c0d2f4b5
Revises: d5f7b9c1e3a4
Create Date: 2026-10-15 10:30:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e6a8c0d2f4b5"
down_revision = "d5f7b9c1e3a4"
branch_labels = None
depends_on = None

INGREDIENTS_CATEGORY = "Nguyên vật liệu"

# name, base unit, purchase unit, base units per purchase unit
BAKERY_ITEMS = (
    ("Trứng gà", "piece", "box", "30"),
    ("Bột mì", "g", "kg", "1000"),
    ("Bột nở", "g", "kg", "1000"),
    ("Siro", "ml", "bottle", "700"),
    ("Sữa tươi", "ml", "l", "1000"),
    ("Đường", "g", "kg", "1000"),
    ("Kem tươi whipping", "ml", "l", "1000"),
    ("Muối", "g", "kg", "1000"),
    ("Tinh chất vani", "ml", "bottle", "100"),
    ("Rượu rum", "ml", "bottle", "700"),
)


def _padded(prefix: str, number_sql: str) -> str:
    """SQL for `<prefix><number>` zero-padded to at least five digits.

    `number_sql` is repeated, so it must not be a volatile call like nextval.
    """
    return (
        f"'{prefix}' || CASE WHEN length(({number_sql})::text) >= 5 "
        f"THEN ({number_sql})::text ELSE lpad(({number_sql})::text, 5, '0') END"
    )


def _assign_codes(table: str, column: str, prefix: str, sequence: str) -> None:
    pattern = f"^{prefix}([0-9]{{5,}})$"
    op.execute(f"CREATE SEQUENCE {sequence} START 1")
    op.execute(
        f"SELECT setval('{sequence}', COALESCE((SELECT max(substring({column} FROM "
        f"'{pattern}')::bigint) FROM {table}), 0) + 1, false)"
    )
    # Renumber legacy codes so the format check holds; order lines keep their
    # snapshot of the old code.
    op.execute(
        f"""
        UPDATE {table} t SET {column} = {_padded(prefix, "s.n")}
        FROM (
            SELECT id, nextval('{sequence}') AS n FROM (
                SELECT id FROM {table} WHERE {column} !~ '{pattern}'
                ORDER BY created_at, id
            ) ordered
        ) s
        WHERE t.id = s.id
        """
    )
    op.create_check_constraint(
        f"ck_{table}_{column}_format", table, f"{column} ~ '^{prefix}[0-9]{{5,}}$'"
    )


def upgrade():
    op.add_column(
        "business_settings",
        sa.Column("language", sa.String(length=2), nullable=False, server_default="en"),
    )
    op.alter_column("business_settings", "language", server_default=None)
    op.create_check_constraint(
        "ck_business_settings_language", "business_settings", "language IN ('en', 'vi')"
    )

    _assign_codes("menu_items", "code", "MENU-", "menu_item_code_seq")
    _assign_codes("inventory_items", "sku", "SP-", "inventory_item_sku_seq")

    connection = op.get_bind()
    category_id = connection.execute(
        sa.text("SELECT id FROM inventory_categories WHERE name = :name"),
        {"name": INGREDIENTS_CATEGORY},
    ).scalar_one()
    for name, base_unit, purchase_unit, factor in BAKERY_ITEMS:
        connection.execute(
            sa.text(
                f"""
                WITH item AS (
                    INSERT INTO inventory_items (
                        id, sku, name, category_id, item_type, base_unit,
                        purchase_unit, conversion_factor, min_stock, is_active,
                        created_at, updated_at
                    )
                    SELECT
                        gen_random_uuid(), {_padded("SP-", "s.n")},
                        :name, :category_id, 'ingredient', :base_unit,
                        :purchase_unit, CAST(:factor AS numeric), 0, true,
                        now(), now()
                    FROM (SELECT nextval('inventory_item_sku_seq') AS n) s
                    RETURNING id
                )
                INSERT INTO inventory_balances (
                    item_id, quantity, avg_unit_cost, value, updated_at
                )
                SELECT id, 0, 0, 0, now() FROM item
                """
            ).bindparams(
                name=name,
                category_id=category_id,
                base_unit=base_unit,
                purchase_unit=purchase_unit,
                factor=factor,
            )
        )


def downgrade():
    connection = op.get_bind()
    names = [name for name, *_ in BAKERY_ITEMS]
    unused = (
        "name = ANY(:names) AND NOT EXISTS ("
        "SELECT 1 FROM inventory_movements m WHERE m.item_id = inventory_items.id)"
    )
    connection.execute(
        sa.text(
            f"DELETE FROM inventory_balances WHERE item_id IN "
            f"(SELECT id FROM inventory_items WHERE {unused})"
        ),
        {"names": names},
    )
    connection.execute(
        sa.text(f"DELETE FROM inventory_items WHERE {unused}"), {"names": names}
    )

    op.drop_constraint("ck_inventory_items_sku_format", "inventory_items", type_="check")
    op.drop_constraint("ck_menu_items_code_format", "menu_items", type_="check")
    op.execute("DROP SEQUENCE inventory_item_sku_seq")
    op.execute("DROP SEQUENCE menu_item_code_seq")
    op.drop_constraint(
        "ck_business_settings_language", "business_settings", type_="check"
    )
    op.drop_column("business_settings", "language")
