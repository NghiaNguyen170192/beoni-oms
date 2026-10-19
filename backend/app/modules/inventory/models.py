import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Identity,
    Index,
    Numeric,
    Sequence,
)
from sqlmodel import Field, SQLModel

from app.core.db_types import EnumString
from app.models import get_datetime_utc


def _sql_values(enum_class: type[Enum]) -> str:
    return ", ".join(f"'{member.value}'" for member in enum_class)


class ItemType(str, Enum):
    INGREDIENT = "ingredient"
    MERCHANDISE = "merchandise"
    PACKAGING = "packaging"
    CONSUMABLE = "consumable"


class InventoryRole(str, Enum):
    RAW_MATERIAL = "raw_material"
    FINISHED_GOOD = "finished_good"
    GENERAL = "general"


class Unit(str, Enum):
    G = "g"
    KG = "kg"
    ML = "ml"
    L = "l"
    PIECE = "piece"
    PACK = "pack"
    BOTTLE = "bottle"
    CUP = "cup"
    BOX = "box"


class MovementType(str, Enum):
    RECEIPT = "receipt"
    SALE_CONSUMPTION = "sale_consumption"
    PRODUCTION_CONSUMPTION = "production_consumption"
    PRODUCTION_RECEIPT = "production_receipt"
    ADJUSTMENT = "adjustment"
    RETURN = "return"
    REVERSAL = "reversal"


class AdjustmentReason(str, Enum):
    PHYSICAL_COUNT = "physical_count"
    SPOILAGE = "spoilage"
    EXPIRED = "expired"
    DAMAGED = "damaged"
    MISSING = "missing"
    CORRECTION = "correction"


class AdjustmentStatus(str, Enum):
    POSTED = "posted"
    REVERSED = "reversed"


ITEM_SKU_INDEX = "uq_inventory_items_sku"
ITEM_BARCODE_INDEX = "uq_inventory_items_barcode"
ITEM_SKU_PREFIX = "SP-"
# Created by migration; standalone so autogenerate leaves it alone.
ITEM_SKU_SEQUENCE = Sequence("inventory_item_sku_seq")


def _timestamp() -> Any:
    return Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        nullable=False,
    )


class InventoryCategory(SQLModel, table=True):
    __tablename__ = "inventory_categories"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=100, unique=True)
    sort_order: int = 0
    is_active: bool = True


class InventoryItem(SQLModel, table=True):
    """Item definition. Stock lives in `InventoryBalance` and changes only
    through `inventory.service.post_movements`."""

    __tablename__ = "inventory_items"
    __table_args__ = (
        Index(ITEM_SKU_INDEX, "sku", unique=True),
        Index(ITEM_BARCODE_INDEX, "barcode", unique=True),
        CheckConstraint(
            f"sku ~ '^{ITEM_SKU_PREFIX}[0-9]{{5,}}$'",
            name="ck_inventory_items_sku_format",
        ),
        CheckConstraint(
            f"item_type IN ({_sql_values(ItemType)})", name="ck_inventory_items_type"
        ),
        CheckConstraint(
            f"role IN ({_sql_values(InventoryRole)})",
            name="ck_inventory_items_role",
        ),
        CheckConstraint(
            f"base_unit IN ({_sql_values(Unit)})", name="ck_inventory_items_base_unit"
        ),
        CheckConstraint(
            f"purchase_unit IN ({_sql_values(Unit)})",
            name="ck_inventory_items_purchase_unit",
        ),
        CheckConstraint(
            "conversion_factor > 0", name="ck_inventory_items_conversion_positive"
        ),
        CheckConstraint(
            "purchase_unit <> base_unit OR conversion_factor = 1",
            name="ck_inventory_items_same_unit_factor_one",
        ),
        CheckConstraint("min_stock >= 0", name="ck_inventory_items_min_stock"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    sku: str = Field(max_length=64)
    name: str = Field(max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    category_id: uuid.UUID = Field(
        foreign_key="inventory_categories.id", ondelete="RESTRICT", index=True
    )
    item_type: ItemType = Field(sa_type=EnumString(ItemType), nullable=False)  # type: ignore
    role: InventoryRole = Field(
        default=InventoryRole.GENERAL,
        sa_type=EnumString(InventoryRole, length=32),  # type: ignore
        nullable=False,
    )
    base_unit: Unit = Field(sa_type=EnumString(Unit, length=16), nullable=False)  # type: ignore
    purchase_unit: Unit = Field(sa_type=EnumString(Unit, length=16), nullable=False)  # type: ignore
    conversion_factor: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore
    min_stock: Decimal = Field(default=Decimal("0"), sa_type=Numeric(18, 4))  # type: ignore
    is_active: bool = True
    barcode: str | None = Field(default=None, max_length=64)
    created_at: datetime = _timestamp()
    updated_at: datetime = _timestamp()


class InventoryBalance(SQLModel, table=True):
    """Current stock per item; equals the sum of the item's movements."""

    __tablename__ = "inventory_balances"
    __table_args__ = (
        CheckConstraint("avg_unit_cost >= 0", name="ck_inventory_balances_avg_cost"),
    )

    item_id: uuid.UUID = Field(
        foreign_key="inventory_items.id", ondelete="CASCADE", primary_key=True
    )
    quantity: Decimal = Field(default=Decimal("0"), sa_type=Numeric(18, 4))  # type: ignore
    avg_unit_cost: Decimal = Field(default=Decimal("0"), sa_type=Numeric(18, 4))  # type: ignore
    value: Decimal = Field(default=Decimal("0"), sa_type=Numeric(18, 2))  # type: ignore
    updated_at: datetime = _timestamp()


class InventoryMovement(SQLModel, table=True):
    """Append-only stock ledger (UPDATE/DELETE rejected by a trigger)."""

    __tablename__ = "inventory_movements"
    __table_args__ = (
        CheckConstraint(
            "quantity <> 0", name="ck_inventory_movements_quantity_nonzero"
        ),
        CheckConstraint("unit_cost >= 0", name="ck_inventory_movements_unit_cost"),
        CheckConstraint(
            f"movement_type IN ({_sql_values(MovementType)})",
            name="ck_inventory_movements_type",
        ),
        Index("ix_inventory_movements_item_seq", "item_id", "seq"),
        Index("ix_inventory_movements_source", "source_type", "source_id"),
        Index("ix_inventory_movements_occurred_at", "occurred_at"),
        Index("ix_inventory_movements_item_occurred", "item_id", "occurred_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    seq: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(), nullable=False, unique=True),
    )
    item_id: uuid.UUID = Field(foreign_key="inventory_items.id", ondelete="RESTRICT")
    movement_type: MovementType = Field(
        sa_type=EnumString(MovementType),  # type: ignore
        nullable=False,
    )
    quantity: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore
    unit_cost: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore
    value: Decimal = Field(sa_type=Numeric(18, 2))  # type: ignore
    quantity_after: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore
    cost_uncertain: bool = False
    source_type: str = Field(max_length=64)
    source_id: uuid.UUID
    actor_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    occurred_at: datetime = _timestamp()


class StockAdjustment(SQLModel, table=True):
    __tablename__ = "stock_adjustments"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_sql_values(AdjustmentStatus)})",
            name="ck_stock_adjustments_status",
        ),
        CheckConstraint(
            "(status = 'reversed') = (reversed_at IS NOT NULL)",
            name="ck_stock_adjustments_reversed_at",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    number: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(), nullable=False, unique=True),
    )
    status: AdjustmentStatus = Field(
        default=AdjustmentStatus.POSTED,
        sa_type=EnumString(AdjustmentStatus),  # type: ignore
        nullable=False,
    )
    note: str | None = Field(default=None, max_length=500)
    posted_by_id: uuid.UUID = Field(foreign_key="user.id", ondelete="RESTRICT")
    posted_at: datetime = _timestamp()
    reversed_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    reversed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    reversal_note: str | None = Field(default=None, max_length=500)


class StockAdjustmentLine(SQLModel, table=True):
    __tablename__ = "stock_adjustment_lines"
    __table_args__ = (
        CheckConstraint(
            f"reason IN ({_sql_values(AdjustmentReason)})",
            name="ck_stock_adjustment_lines_reason",
        ),
        CheckConstraint(
            "resulting_quantity = previous_quantity + quantity_change",
            name="ck_stock_adjustment_lines_result",
        ),
        CheckConstraint(
            "(reason = 'physical_count') = (counted_quantity IS NOT NULL)",
            name="ck_stock_adjustment_lines_counted",
        ),
        CheckConstraint(
            "(quantity_change = 0) = (movement_id IS NULL)",
            name="ck_stock_adjustment_lines_movement",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    adjustment_id: uuid.UUID = Field(
        foreign_key="stock_adjustments.id", ondelete="RESTRICT", index=True
    )
    line_no: int
    item_id: uuid.UUID = Field(
        foreign_key="inventory_items.id", ondelete="RESTRICT", index=True
    )
    reason: AdjustmentReason = Field(
        sa_type=EnumString(AdjustmentReason),  # type: ignore
        nullable=False,
    )
    counted_quantity: Decimal | None = Field(default=None, sa_type=Numeric(18, 4))  # type: ignore
    previous_quantity: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore
    quantity_change: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore
    resulting_quantity: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore
    unit_cost: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore
    movement_id: uuid.UUID | None = Field(
        default=None, foreign_key="inventory_movements.id", ondelete="RESTRICT"
    )
