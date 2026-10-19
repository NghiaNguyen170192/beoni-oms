import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Identity,
    Index,
    Numeric,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel

from app.core.db_types import EnumString
from app.models import get_datetime_utc
from app.modules.inventory.models import Unit


def _sql_values(enum_class: type[Enum]) -> str:
    return ", ".join(f"'{member.value}'" for member in enum_class)


def _timestamp() -> Any:
    return Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        nullable=False,
    )


def _optional_timestamp() -> Any:
    return Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore


class ProductionBatchStatus(str, Enum):
    DRAFT = "draft"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REVERSED = "reversed"


class FinishedGoodLotOrigin(str, Enum):
    PRODUCTION = "production"
    OPENING_STOCK = "opening_stock"


class ProductionBatch(SQLModel, table=True):
    __tablename__ = "production_batches"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_sql_values(ProductionBatchStatus)})",
            name="ck_production_batches_status",
        ),
        CheckConstraint(
            "(status IN ('completed', 'reversed')) = (finished_at IS NOT NULL)",
            name="ck_production_batches_finished_at",
        ),
        CheckConstraint(
            "(status IN ('completed', 'reversed')) = (completed_by_id IS NOT NULL)",
            name="ck_production_batches_completed_by",
        ),
        CheckConstraint(
            "(status = 'reversed' AND reversed_at IS NOT NULL "
            "AND reversed_by_id IS NOT NULL AND reversal_reason IS NOT NULL) OR "
            "(status <> 'reversed' AND reversed_at IS NULL "
            "AND reversed_by_id IS NULL AND reversal_reason IS NULL)",
            name="ck_production_batches_reversal_metadata",
        ),
        CheckConstraint(
            "formula_runs IS NULL OR formula_runs > 0",
            name="ck_production_batches_formula_runs_positive",
        ),
        CheckConstraint(
            "(recipe_id IS NULL) = (formula_runs IS NULL)",
            name="ck_production_batches_formula_runs_source",
        ),
        CheckConstraint(
            "total_material_cost IS NULL OR total_material_cost >= 0",
            name="ck_production_batches_total_material_cost",
        ),
        Index("ix_production_batches_status", "status"),
        Index("ix_production_batches_planned_for", "planned_for"),
        Index("ix_production_batches_finished_at", "finished_at"),
        Index("ix_production_batches_recipe", "recipe_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    number: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(), nullable=False, unique=True),
    )
    status: ProductionBatchStatus = Field(
        default=ProductionBatchStatus.DRAFT,
        sa_type=EnumString(ProductionBatchStatus),  # type: ignore
        nullable=False,
    )
    recipe_id: uuid.UUID | None = Field(
        default=None, foreign_key="recipes.id", ondelete="RESTRICT"
    )
    formula_runs: Decimal | None = Field(
        default=None, sa_type=Numeric(18, 4)  # type: ignore
    )
    total_material_cost: Decimal | None = Field(
        default=None, sa_type=Numeric(18, 2)  # type: ignore
    )
    cost_uncertain: bool = False
    planned_for: date = Field(sa_type=Date, nullable=False)  # type: ignore
    finished_at: datetime | None = _optional_timestamp()
    notes: str | None = Field(default=None, max_length=1000)
    created_by_id: uuid.UUID = Field(foreign_key="user.id", ondelete="RESTRICT")
    completed_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    reversed_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    reversed_at: datetime | None = _optional_timestamp()
    reversal_reason: str | None = Field(default=None, max_length=255)
    created_at: datetime = _timestamp()
    updated_at: datetime = _timestamp()


class ProductionBatchTemplate(SQLModel, table=True):
    __tablename__ = "production_batch_templates"
    __table_args__ = (
        CheckConstraint(
            "formula_runs IS NULL OR formula_runs > 0",
            name="ck_production_batch_templates_formula_runs_positive",
        ),
        CheckConstraint(
            "(recipe_id IS NULL) = (formula_runs IS NULL)",
            name="ck_production_batch_templates_formula_runs_source",
        ),
        Index("ix_production_batch_templates_name", "name"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=120, nullable=False)
    recipe_id: uuid.UUID | None = Field(
        default=None, foreign_key="recipes.id", ondelete="RESTRICT"
    )
    formula_runs: Decimal | None = Field(
        default=None,
        sa_type=Numeric(18, 4),  # type: ignore
    )
    created_by_id: uuid.UUID = Field(foreign_key="user.id", ondelete="RESTRICT")
    created_at: datetime = _timestamp()
    updated_at: datetime = _timestamp()


class ProductionBatchTemplateIngredientLine(SQLModel, table=True):
    __tablename__ = "production_batch_template_ingredient_lines"
    __table_args__ = (
        UniqueConstraint(
            "template_id", "line_no", name="uq_production_template_ingredient_line_no"
        ),
        UniqueConstraint(
            "template_id",
            "inventory_item_id",
            name="uq_production_template_ingredient_item",
        ),
        CheckConstraint(
            "line_no > 0", name="ck_production_template_ingredient_line_no"
        ),
        CheckConstraint(
            "planned_quantity > 0",
            name="ck_production_template_ingredient_planned_positive",
        ),
        Index("ix_production_template_ingredient_item", "inventory_item_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    template_id: uuid.UUID = Field(
        foreign_key="production_batch_templates.id", ondelete="CASCADE", index=True
    )
    line_no: int
    inventory_item_id: uuid.UUID = Field(
        foreign_key="inventory_items.id", ondelete="RESTRICT"
    )
    planned_quantity: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore


class ProductionBatchTemplateOutputLine(SQLModel, table=True):
    __tablename__ = "production_batch_template_output_lines"
    __table_args__ = (
        UniqueConstraint(
            "template_id", "line_no", name="uq_production_template_output_line_no"
        ),
        UniqueConstraint(
            "template_id", "menu_item_id", name="uq_production_template_output_menu"
        ),
        CheckConstraint("line_no > 0", name="ck_production_template_output_line_no"),
        CheckConstraint(
            "planned_quantity > 0",
            name="ck_production_template_output_planned_positive",
        ),
        Index("ix_production_template_output_menu", "menu_item_id"),
        Index("ix_production_template_output_inventory", "inventory_item_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    template_id: uuid.UUID = Field(
        foreign_key="production_batch_templates.id", ondelete="CASCADE", index=True
    )
    line_no: int
    menu_item_id: uuid.UUID = Field(foreign_key="menu_items.id", ondelete="RESTRICT")
    inventory_item_id: uuid.UUID = Field(
        foreign_key="inventory_items.id", ondelete="RESTRICT"
    )
    planned_quantity: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore


class ProductionBatchIngredientLine(SQLModel, table=True):
    __tablename__ = "production_batch_ingredient_lines"
    __table_args__ = (
        UniqueConstraint(
            "batch_id", "line_no", name="uq_production_batch_ingredient_line_no"
        ),
        UniqueConstraint(
            "batch_id", "inventory_item_id", name="uq_production_batch_ingredient_item"
        ),
        CheckConstraint("line_no > 0", name="ck_production_batch_ingredient_line_no"),
        CheckConstraint(
            "planned_quantity > 0",
            name="ck_production_batch_ingredient_planned_positive",
        ),
        CheckConstraint(
            "actual_quantity IS NULL OR actual_quantity >= 0",
            name="ck_production_batch_ingredient_actual_nonnegative",
        ),
        CheckConstraint(
            "(actual_quantity IS NULL OR actual_quantity = 0) = (movement_id IS NULL)",
            name="ck_production_batch_ingredient_movement",
        ),
        Index("ix_production_batch_ingredient_item", "inventory_item_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    batch_id: uuid.UUID = Field(
        foreign_key="production_batches.id", ondelete="RESTRICT", index=True
    )
    line_no: int
    inventory_item_id: uuid.UUID = Field(
        foreign_key="inventory_items.id", ondelete="RESTRICT"
    )
    unit: Unit = Field(sa_type=EnumString(Unit, length=16), nullable=False)  # type: ignore
    planned_quantity: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore
    actual_quantity: Decimal | None = Field(
        default=None, sa_type=Numeric(18, 4)  # type: ignore
    )
    movement_id: uuid.UUID | None = Field(
        default=None, foreign_key="inventory_movements.id", ondelete="RESTRICT"
    )


class ProductionBatchOutputLine(SQLModel, table=True):
    __tablename__ = "production_batch_output_lines"
    __table_args__ = (
        UniqueConstraint("batch_id", "line_no", name="uq_production_batch_output_no"),
        UniqueConstraint(
            "batch_id", "menu_item_id", name="uq_production_batch_output_menu_item"
        ),
        CheckConstraint("line_no > 0", name="ck_production_batch_output_line_no"),
        CheckConstraint(
            "planned_quantity > 0",
            name="ck_production_batch_output_planned_positive",
        ),
        CheckConstraint(
            "actual_good_quantity IS NULL OR actual_good_quantity >= 0",
            name="ck_production_batch_output_good_nonnegative",
        ),
        CheckConstraint(
            "waste_quantity >= 0", name="ck_production_batch_output_waste_nonnegative"
        ),
        CheckConstraint(
            "unit_cost IS NULL OR unit_cost >= 0",
            name="ck_production_batch_output_unit_cost",
        ),
        CheckConstraint(
            "(actual_good_quantity IS NULL OR actual_good_quantity = 0) = "
            "(movement_id IS NULL)",
            name="ck_production_batch_output_movement",
        ),
        Index("ix_production_batch_output_inventory_item", "inventory_item_id"),
        Index("ix_production_batch_output_menu_item", "menu_item_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    batch_id: uuid.UUID = Field(
        foreign_key="production_batches.id", ondelete="RESTRICT", index=True
    )
    line_no: int
    menu_item_id: uuid.UUID = Field(foreign_key="menu_items.id", ondelete="RESTRICT")
    inventory_item_id: uuid.UUID = Field(
        foreign_key="inventory_items.id", ondelete="RESTRICT"
    )
    unit: Unit = Field(sa_type=EnumString(Unit, length=16), nullable=False)  # type: ignore
    planned_quantity: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore
    actual_good_quantity: Decimal | None = Field(
        default=None, sa_type=Numeric(18, 4)  # type: ignore
    )
    waste_quantity: Decimal = Field(
        default=Decimal("0"), sa_type=Numeric(18, 4)  # type: ignore
    )
    unit_cost: Decimal | None = Field(
        default=None, sa_type=Numeric(18, 4)  # type: ignore
    )
    cost_uncertain: bool = True
    movement_id: uuid.UUID | None = Field(
        default=None, foreign_key="inventory_movements.id", ondelete="RESTRICT"
    )


class FinishedGoodLot(SQLModel, table=True):
    __tablename__ = "finished_good_lots"
    __table_args__ = (
        CheckConstraint(
            f"origin IN ({_sql_values(FinishedGoodLotOrigin)})",
            name="ck_finished_good_lots_origin",
        ),
        CheckConstraint(
            "(origin = 'production' AND batch_id IS NOT NULL "
            "AND output_line_id IS NOT NULL AND opening_stock_line_id IS NULL) OR "
            "(origin = 'opening_stock' AND batch_id IS NULL "
            "AND output_line_id IS NULL AND opening_stock_line_id IS NOT NULL)",
            name="ck_finished_good_lots_source",
        ),
        CheckConstraint(
            "produced_quantity > 0 AND quantity_on_hand >= 0 "
            "AND reserved_quantity >= 0 AND reserved_quantity <= quantity_on_hand",
            name="ck_finished_good_lots_quantities",
        ),
        CheckConstraint(
            "unit_cost IS NULL OR unit_cost >= 0",
            name="ck_finished_good_lots_unit_cost",
        ),
        Index("ix_finished_good_lots_item_finished", "inventory_item_id", "finished_at"),
        Index("ix_finished_good_lots_expiry", "expiry_date"),
        Index("ix_finished_good_lots_batch", "batch_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    lot_number: str = Field(max_length=64, unique=True)
    origin: FinishedGoodLotOrigin = Field(
        sa_type=EnumString(FinishedGoodLotOrigin),  # type: ignore
        nullable=False,
    )
    batch_id: uuid.UUID | None = Field(
        default=None, foreign_key="production_batches.id", ondelete="RESTRICT"
    )
    output_line_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="production_batch_output_lines.id",
        ondelete="RESTRICT",
        unique=True,
    )
    opening_stock_line_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="stock_adjustment_lines.id",
        ondelete="RESTRICT",
        unique=True,
    )
    inventory_item_id: uuid.UUID = Field(
        foreign_key="inventory_items.id", ondelete="RESTRICT", index=True
    )
    produced_quantity: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore
    quantity_on_hand: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore
    reserved_quantity: Decimal = Field(
        default=Decimal("0"), sa_type=Numeric(18, 4)  # type: ignore
    )
    unit_cost: Decimal | None = Field(
        default=None, sa_type=Numeric(18, 4)  # type: ignore
    )
    finished_at: datetime = Field(sa_type=DateTime(timezone=True))  # type: ignore
    expiry_date: date | None = Field(default=None, sa_type=Date)  # type: ignore
    created_at: datetime = _timestamp()
    updated_at: datetime = _timestamp()


class FinishedGoodLotMovement(SQLModel, table=True):
    __tablename__ = "finished_good_lot_movements"
    __table_args__ = (
        UniqueConstraint(
            "lot_id", "movement_id", name="uq_finished_good_lot_movement"
        ),
        CheckConstraint("quantity <> 0", name="ck_finished_good_lot_movement_quantity"),
        Index("ix_finished_good_lot_movements_movement", "movement_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    lot_id: uuid.UUID = Field(
        foreign_key="finished_good_lots.id", ondelete="RESTRICT", index=True
    )
    movement_id: uuid.UUID = Field(
        foreign_key="inventory_movements.id", ondelete="RESTRICT"
    )
    quantity: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore
    created_at: datetime = _timestamp()


class FinishedGoodLotAllocation(SQLModel, table=True):
    __tablename__ = "finished_good_lot_allocations"
    __table_args__ = (
        UniqueConstraint(
            "lot_movement_id",
            "order_line_id",
            name="uq_finished_good_lot_allocation",
        ),
        CheckConstraint("quantity > 0", name="ck_finished_good_lot_allocation_quantity"),
        Index("ix_finished_good_lot_allocations_order_line", "order_line_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    lot_movement_id: uuid.UUID = Field(
        foreign_key="finished_good_lot_movements.id", ondelete="RESTRICT"
    )
    order_line_id: uuid.UUID = Field(
        foreign_key="order_lines.id", ondelete="RESTRICT"
    )
    quantity: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore
    created_at: datetime = _timestamp()
