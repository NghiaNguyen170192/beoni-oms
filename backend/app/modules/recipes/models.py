import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.db_types import EnumString
from app.models import get_datetime_utc


class RecipeKind(str, Enum):
    RECIPE = "recipe"
    STOCK_LINK = "stock_link"


def _sql_values(enum_class: type[Enum]) -> str:
    return ", ".join(f"'{member.value}'" for member in enum_class)


def _timestamp() -> Any:
    return Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        nullable=False,
    )


class Recipe(SQLModel, table=True):
    """One version of a menu item's consumption definition.

    `recipe` is a prepared item's ingredient list and optional production
    outputs. `stock_link` is a direct-sale item's single inventory item and
    quantity per unit sold.
    """

    __tablename__ = "recipes"
    __table_args__ = (
        UniqueConstraint("menu_item_id", "version", name="uq_recipes_item_version"),
        UniqueConstraint(
            "menu_item_id", "effective_from", name="uq_recipes_item_effective"
        ),
        CheckConstraint("version > 0", name="ck_recipes_version_positive"),
        CheckConstraint(
            f"kind IN ({_sql_values(RecipeKind)})", name="ck_recipes_kind"
        ),
        Index("ix_recipes_item_effective", "menu_item_id", "effective_from"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    menu_item_id: uuid.UUID = Field(
        foreign_key="menu_items.id", ondelete="RESTRICT", index=True
    )
    version: int
    kind: RecipeKind = Field(sa_type=EnumString(RecipeKind), nullable=False)  # type: ignore
    effective_from: datetime = Field(sa_type=DateTime(timezone=True))  # type: ignore
    created_by_id: uuid.UUID = Field(foreign_key="user.id", ondelete="RESTRICT")
    created_at: datetime = _timestamp()


class RecipeLine(SQLModel, table=True):
    __tablename__ = "recipe_lines"
    __table_args__ = (
        UniqueConstraint(
            "recipe_id", "inventory_item_id", name="uq_recipe_lines_item"
        ),
        CheckConstraint("quantity > 0", name="ck_recipe_lines_quantity_positive"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    recipe_id: uuid.UUID = Field(
        foreign_key="recipes.id", ondelete="RESTRICT", index=True
    )
    inventory_item_id: uuid.UUID = Field(
        foreign_key="inventory_items.id", ondelete="RESTRICT"
    )
    quantity: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore


class RecipeOutputLine(SQLModel, table=True):
    __tablename__ = "recipe_output_lines"
    __table_args__ = (
        UniqueConstraint(
            "recipe_id", "menu_item_id", name="uq_recipe_output_lines_menu_item"
        ),
        CheckConstraint(
            "quantity > 0", name="ck_recipe_output_lines_quantity_positive"
        ),
        Index("ix_recipe_output_lines_menu_item", "menu_item_id"),
        Index("ix_recipe_output_lines_inventory_item", "inventory_item_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    recipe_id: uuid.UUID = Field(
        foreign_key="recipes.id", ondelete="RESTRICT", index=True
    )
    menu_item_id: uuid.UUID = Field(
        foreign_key="menu_items.id", ondelete="RESTRICT"
    )
    inventory_item_id: uuid.UUID = Field(
        foreign_key="inventory_items.id", ondelete="RESTRICT"
    )
    quantity: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore


class MovementAllocation(SQLModel, table=True):
    """How much of a sale movement belongs to one order line.

    Quantities and values are signed like the movement, so they sum back to it.
    """

    __tablename__ = "movement_allocations"
    __table_args__ = (
        UniqueConstraint(
            "movement_id", "order_line_id", name="uq_movement_allocations_line"
        ),
        CheckConstraint(
            "quantity <> 0", name="ck_movement_allocations_quantity_nonzero"
        ),
        Index("ix_movement_allocations_order_line", "order_line_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    movement_id: uuid.UUID = Field(
        foreign_key="inventory_movements.id", ondelete="RESTRICT"
    )
    order_line_id: uuid.UUID = Field(
        foreign_key="order_lines.id", ondelete="RESTRICT"
    )
    quantity: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore
    value: Decimal = Field(sa_type=Numeric(18, 2))  # type: ignore


class StockReturn(SQLModel, table=True):
    __tablename__ = "stock_returns"
    __table_args__ = (Index("ix_stock_returns_order", "order_id"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    order_id: uuid.UUID = Field(foreign_key="orders.id", ondelete="RESTRICT")
    reason: str = Field(max_length=255)
    created_by_id: uuid.UUID = Field(foreign_key="user.id", ondelete="RESTRICT")
    created_at: datetime = _timestamp()


class StockReturnLine(SQLModel, table=True):
    __tablename__ = "stock_return_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_stock_return_lines_quantity"),
        CheckConstraint(
            "(sellable AND movement_id IS NOT NULL) OR "
            "(NOT sellable AND movement_id IS NULL)",
            name="ck_stock_return_lines_movement",
        ),
        CheckConstraint(
            "(finished_good_lot_id IS NULL) = "
            "(finished_good_lot_allocation_id IS NULL)",
            name="ck_stock_return_lines_finished_good_lot",
        ),
        Index("ix_stock_return_lines_order_line", "order_line_id"),
        Index(
            "ix_stock_return_lines_finished_good_allocation",
            "finished_good_lot_allocation_id",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    stock_return_id: uuid.UUID = Field(
        foreign_key="stock_returns.id", ondelete="RESTRICT", index=True
    )
    order_line_id: uuid.UUID = Field(
        foreign_key="order_lines.id", ondelete="RESTRICT"
    )
    quantity: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore
    sellable: bool
    unit_cost: Decimal | None = Field(
        default=None, sa_type=Numeric(18, 4)  # type: ignore
    )
    movement_id: uuid.UUID | None = Field(
        default=None, foreign_key="inventory_movements.id", ondelete="RESTRICT"
    )
    finished_good_lot_id: uuid.UUID | None = Field(
        default=None, foreign_key="finished_good_lots.id", ondelete="RESTRICT"
    )
    finished_good_lot_allocation_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="finished_good_lot_allocations.id",
        ondelete="RESTRICT",
    )
