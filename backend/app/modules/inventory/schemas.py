import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import field_validator, model_validator
from sqlmodel import Field, SQLModel
from typing_extensions import Self

from app.modules.inventory.models import (
    AdjustmentReason,
    AdjustmentStatus,
    InventoryRole,
    ItemType,
    MovementType,
    Unit,
)

DECREASE_REASONS = frozenset(
    {
        AdjustmentReason.SPOILAGE,
        AdjustmentReason.EXPIRED,
        AdjustmentReason.DAMAGED,
        AdjustmentReason.MISSING,
    }
)
MAX_ADJUSTMENT_LINES = 200


def _strip_required(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError("Must not be blank")
    return value


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


# Categories


class InventoryCategoryPublic(SQLModel):
    id: uuid.UUID
    name: str
    sort_order: int
    is_active: bool


class InventoryCategoriesPublic(SQLModel):
    data: list[InventoryCategoryPublic]
    count: int


# Items


class InventoryItemCreate(SQLModel):
    """The SKU is assigned by the system."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    category_id: uuid.UUID
    item_type: ItemType
    role: InventoryRole | None = None
    base_unit: Unit
    purchase_unit: Unit
    conversion_factor: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    min_stock: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=18, decimal_places=4
    )
    is_active: bool = True
    barcode: str | None = Field(default=None, max_length=64)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str | None:
        return _strip_required(value)

    @field_validator("description", "barcode")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @model_validator(mode="after")
    def same_unit_needs_factor_one(self) -> Self:
        if self.purchase_unit == self.base_unit and self.conversion_factor != 1:
            raise ValueError(
                "Conversion factor must be 1 when purchase and base units are equal"
            )
        if self.role is None:
            self.role = (
                InventoryRole.RAW_MATERIAL
                if self.item_type
                in {ItemType.INGREDIENT, ItemType.PACKAGING, ItemType.CONSUMABLE}
                else InventoryRole.GENERAL
            )
        return self


class InventoryItemUpdate(SQLModel):
    """Definition fields only; quantity and cost change through movements and
    the SKU never changes."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    category_id: uuid.UUID | None = None
    item_type: ItemType | None = None
    role: InventoryRole | None = None
    base_unit: Unit | None = None
    purchase_unit: Unit | None = None
    conversion_factor: Decimal | None = Field(
        default=None, gt=0, max_digits=18, decimal_places=4
    )
    min_stock: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=4
    )
    is_active: bool | None = None
    barcode: str | None = Field(default=None, max_length=64)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return _strip_required(value)

    @field_validator("description", "barcode")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class InventoryItemPublic(SQLModel):
    id: uuid.UUID
    sku: str
    name: str
    description: str | None
    category_id: uuid.UUID
    item_type: ItemType
    role: InventoryRole
    base_unit: Unit
    purchase_unit: Unit
    conversion_factor: Decimal
    min_stock: Decimal
    is_active: bool
    barcode: str | None
    created_at: datetime
    updated_at: datetime
    quantity: Decimal
    avg_unit_cost: Decimal
    value: Decimal
    is_low_stock: bool
    is_negative_stock: bool


class InventoryItemsPublic(SQLModel):
    data: list[InventoryItemPublic]
    count: int


class FinishedGoodLotPublic(SQLModel):
    id: uuid.UUID
    lot_number: str
    origin: str
    batch_id: uuid.UUID | None
    batch_number: int | None
    inventory_item_id: uuid.UUID
    produced_quantity: Decimal
    quantity_on_hand: Decimal
    reserved_quantity: Decimal
    available_quantity: Decimal
    unit_cost: Decimal | None
    finished_at: datetime
    expiry_date: date | None


class FinishedGoodLotsPublic(SQLModel):
    data: list[FinishedGoodLotPublic]
    count: int


# Movements


class InventoryMovementPublic(SQLModel):
    id: uuid.UUID
    seq: int
    item_id: uuid.UUID
    movement_type: MovementType
    quantity: Decimal
    unit_cost: Decimal
    value: Decimal
    quantity_after: Decimal
    cost_uncertain: bool
    source_type: str
    source_id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_email: str | None
    actor_name: str | None
    occurred_at: datetime


class InventoryMovementsPublic(SQLModel):
    data: list[InventoryMovementPublic]
    count: int


# Adjustments


class StockAdjustmentLineCreate(SQLModel):
    item_id: uuid.UUID
    reason: AdjustmentReason
    quantity_change: Decimal | None = Field(
        default=None, max_digits=18, decimal_places=4
    )
    counted_quantity: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=4
    )
    unit_cost: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=4
    )

    @model_validator(mode="after")
    def check_reason_fields(self) -> Self:
        if self.reason == AdjustmentReason.PHYSICAL_COUNT:
            if self.counted_quantity is None or self.quantity_change is not None:
                raise ValueError("A physical count line needs counted_quantity only")
            return self
        if self.counted_quantity is not None:
            raise ValueError("counted_quantity is only for physical_count lines")
        if self.quantity_change is None or self.quantity_change == 0:
            raise ValueError("quantity_change must be non-zero")
        if self.reason in DECREASE_REASONS and self.quantity_change > 0:
            raise ValueError(f"A {self.reason.value} adjustment must decrease stock")
        if self.unit_cost is not None and self.quantity_change < 0:
            raise ValueError("unit_cost applies only to increases")
        return self


class StockAdjustmentCreate(SQLModel):
    note: str | None = Field(default=None, max_length=500)
    lines: list[StockAdjustmentLineCreate] = Field(
        min_length=1, max_length=MAX_ADJUSTMENT_LINES
    )

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @model_validator(mode="after")
    def unique_items(self) -> Self:
        item_ids = [line.item_id for line in self.lines]
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("Each item may appear only once per adjustment")
        return self


class StockAdjustmentReverse(SQLModel):
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class StockAdjustmentLinePublic(SQLModel):
    id: uuid.UUID
    line_no: int
    item_id: uuid.UUID
    item_sku: str
    item_name: str
    base_unit: Unit
    reason: AdjustmentReason
    counted_quantity: Decimal | None
    previous_quantity: Decimal
    quantity_change: Decimal
    resulting_quantity: Decimal
    unit_cost: Decimal
    movement_id: uuid.UUID | None


class StockAdjustmentPublic(SQLModel):
    id: uuid.UUID
    number: int
    status: AdjustmentStatus
    note: str | None
    posted_by_id: uuid.UUID
    posted_by_email: str | None
    posted_by_name: str | None
    posted_at: datetime
    reversed_by_id: uuid.UUID | None
    reversed_at: datetime | None
    reversal_note: str | None
    lines: list[StockAdjustmentLinePublic]


class StockAdjustmentSummary(SQLModel):
    id: uuid.UUID
    number: int
    status: AdjustmentStatus
    note: str | None
    posted_by_email: str | None
    posted_by_name: str | None
    posted_at: datetime
    reversed_at: datetime | None
    line_count: int


class StockAdjustmentsPublic(SQLModel):
    data: list[StockAdjustmentSummary]
    count: int
