import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import field_validator, model_validator
from sqlmodel import Field, SQLModel
from typing_extensions import Self

from app.modules.inventory.models import Unit
from app.modules.production.models import ProductionBatchStatus


class BatchIngredientCreate(SQLModel):
    inventory_item_id: uuid.UUID
    planned_quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)


class BatchOutputCreate(SQLModel):
    menu_item_id: uuid.UUID
    inventory_item_id: uuid.UUID
    planned_quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)


class BatchIngredientActual(SQLModel):
    line_id: uuid.UUID
    actual_quantity: Decimal = Field(ge=0, max_digits=18, decimal_places=4)


class BatchOutputActual(SQLModel):
    line_id: uuid.UUID
    actual_good_quantity: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    waste_quantity: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=18, decimal_places=4
    )


class ProductionBatchComplete(SQLModel):
    finished_at: datetime | None = None
    ingredients: list[BatchIngredientActual] = Field(min_length=1, max_length=100)
    outputs: list[BatchOutputActual] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_completion(self) -> Self:
        if self.finished_at is not None and self.finished_at.utcoffset() is None:
            raise ValueError("finished_at must include a timezone")
        ingredient_ids = [line.line_id for line in self.ingredients]
        if len(set(ingredient_ids)) != len(ingredient_ids):
            raise ValueError("Each ingredient line can appear only once")
        output_ids = [line.line_id for line in self.outputs]
        if len(set(output_ids)) != len(output_ids):
            raise ValueError("Each output line can appear only once")
        return self


class ProductionBatchReverse(SQLModel):
    reason: str = Field(min_length=1, max_length=255)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("reason must not be blank")
        return cleaned


class ProductionBatchCreate(SQLModel):
    planned_for: date
    notes: str | None = Field(default=None, max_length=1000)
    recipe_id: uuid.UUID | None = None
    formula_runs: Decimal | None = Field(
        default=None, gt=0, max_digits=18, decimal_places=4
    )
    ingredients: list[BatchIngredientCreate] | None = Field(
        default=None, min_length=1, max_length=100
    )
    outputs: list[BatchOutputCreate] | None = Field(
        default=None, min_length=1, max_length=100
    )

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        if self.recipe_id is not None:
            if (
                self.formula_runs is None
                or self.ingredients is not None
                or self.outputs is None
            ):
                raise ValueError(
                    "Formula batches require a run count and selected output lines"
                )
        else:
            if (
                self.formula_runs is not None
                or self.ingredients is None
                or self.outputs is None
            ):
                raise ValueError(
                    "Manual batches require ingredient and output lines without a formula"
                )
            ingredient_ids = [line.inventory_item_id for line in self.ingredients]
            if len(set(ingredient_ids)) != len(ingredient_ids):
                raise ValueError("Each ingredient inventory item can appear only once")
        assert self.outputs is not None
        output_menu_ids = [line.menu_item_id for line in self.outputs]
        if len(set(output_menu_ids)) != len(output_menu_ids):
            raise ValueError("Each menu item can appear only once in outputs")
        return self


class ProductionBatchUpdate(SQLModel):
    planned_for: date | None = None
    notes: str | None = Field(default=None, max_length=1000)
    recipe_id: uuid.UUID | None = None
    formula_runs: Decimal | None = Field(
        default=None, gt=0, max_digits=18, decimal_places=4
    )
    ingredients: list[BatchIngredientCreate] | None = Field(
        default=None, min_length=1, max_length=100
    )
    outputs: list[BatchOutputCreate] | None = Field(
        default=None, min_length=1, max_length=100
    )

    @model_validator(mode="after")
    def unique_lines(self) -> Self:
        formula_fields = {"recipe_id", "formula_runs"}
        formula_fields_set = formula_fields.intersection(self.model_fields_set)
        if formula_fields_set and formula_fields_set != formula_fields:
            raise ValueError(
                "Formula selection and run count must be updated together"
            )
        if "recipe_id" in self.model_fields_set:
            if self.recipe_id is None:
                if (
                    self.formula_runs is not None
                    or self.ingredients is None
                    or self.outputs is None
                ):
                    raise ValueError(
                        "Clearing a formula requires manual ingredient and output lines"
                    )
            elif (
                self.formula_runs is None
                or self.ingredients is not None
                or self.outputs is None
            ):
                raise ValueError(
                    "Formula updates require a run count and selected output lines"
                )
        if self.ingredients is not None:
            ingredient_ids = [line.inventory_item_id for line in self.ingredients]
            if len(set(ingredient_ids)) != len(ingredient_ids):
                raise ValueError("Each ingredient inventory item can appear only once")
        if self.outputs is not None:
            output_menu_ids = [line.menu_item_id for line in self.outputs]
            if len(set(output_menu_ids)) != len(output_menu_ids):
                raise ValueError("Each menu item can appear only once in outputs")
        return self


class ProductionBatchTemplateCreate(SQLModel):
    name: str = Field(min_length=1, max_length=120)
    recipe_id: uuid.UUID | None = None
    formula_runs: Decimal | None = Field(
        default=None, gt=0, max_digits=18, decimal_places=4
    )
    ingredients: list[BatchIngredientCreate] | None = Field(
        default=None, min_length=1, max_length=100
    )
    outputs: list[BatchOutputCreate] = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name must not be blank")
        return cleaned

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        if self.recipe_id is not None:
            if self.formula_runs is None or self.ingredients is not None:
                raise ValueError(
                    "Formula templates require a run count and no manual ingredients"
                )
        elif self.formula_runs is not None or self.ingredients is None:
            raise ValueError(
                "Manual templates require ingredient lines without a formula"
            )
        if self.ingredients is not None:
            ingredient_ids = [line.inventory_item_id for line in self.ingredients]
            if len(set(ingredient_ids)) != len(ingredient_ids):
                raise ValueError("Each ingredient inventory item can appear only once")
        output_menu_ids = [line.menu_item_id for line in self.outputs]
        if len(set(output_menu_ids)) != len(output_menu_ids):
            raise ValueError("Each menu item can appear only once in outputs")
        return self


class BatchIngredientPublic(SQLModel):
    id: uuid.UUID
    line_no: int
    inventory_item_id: uuid.UUID
    item_sku: str
    item_name: str
    unit: Unit
    planned_quantity: Decimal
    actual_quantity: Decimal | None


class BatchOutputPublic(SQLModel):
    id: uuid.UUID
    line_no: int
    menu_item_id: uuid.UUID
    menu_item_name: str
    menu_item_code: str
    inventory_item_id: uuid.UUID
    item_sku: str
    item_name: str
    unit: Unit
    planned_quantity: Decimal
    actual_good_quantity: Decimal | None
    waste_quantity: Decimal
    unit_cost: Decimal | None
    cost_uncertain: bool


class ProductionBatchSummary(SQLModel):
    id: uuid.UUID
    number: int
    status: ProductionBatchStatus
    recipe_id: uuid.UUID | None
    formula_runs: Decimal | None
    total_material_cost: Decimal | None
    cost_uncertain: bool
    planned_for: date
    finished_at: datetime | None
    created_at: datetime


class ProductionBatchPublic(SQLModel):
    id: uuid.UUID
    number: int
    status: ProductionBatchStatus
    recipe_id: uuid.UUID | None
    formula_runs: Decimal | None
    total_material_cost: Decimal | None
    cost_uncertain: bool
    planned_for: date
    finished_at: datetime | None
    notes: str | None
    created_by_id: uuid.UUID
    completed_by_id: uuid.UUID | None
    reversed_by_id: uuid.UUID | None
    reversed_at: datetime | None
    reversal_reason: str | None
    created_at: datetime
    updated_at: datetime
    ingredients: list[BatchIngredientPublic]
    outputs: list[BatchOutputPublic]


class ProductionBatchTemplatePublic(SQLModel):
    id: uuid.UUID
    name: str
    recipe_id: uuid.UUID | None
    recipe_menu_item_id: uuid.UUID | None
    formula_runs: Decimal | None
    ingredients: list[BatchIngredientCreate]
    outputs: list[BatchOutputCreate]
    created_by_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ProductionBatchTemplatesPublic(SQLModel):
    data: list[ProductionBatchTemplatePublic]
    count: int


class ProductionLotReturnTracePublic(SQLModel):
    stock_return_line_id: uuid.UUID
    stock_return_id: uuid.UUID
    order_line_id: uuid.UUID
    quantity: Decimal
    sellable: bool
    reason: str
    returned_at: datetime


class ProductionLotOrderTracePublic(SQLModel):
    order_id: uuid.UUID
    order_number: str
    order_status: str
    completed_at: datetime | None
    order_line_id: uuid.UUID
    item_name: str
    allocated_quantity: Decimal
    returned_quantity: Decimal
    returns: list[ProductionLotReturnTracePublic]


class ProductionBatchLotTracePublic(SQLModel):
    lot_id: uuid.UUID
    lot_number: str
    inventory_item_id: uuid.UUID
    item_name: str
    produced_quantity: Decimal
    quantity_on_hand: Decimal
    available_quantity: Decimal
    finished_at: datetime
    expiry_date: date | None
    orders: list[ProductionLotOrderTracePublic]


class ProductionBatchTraceabilityPublic(SQLModel):
    batch: ProductionBatchPublic
    lots: list[ProductionBatchLotTracePublic]


class ProductionBatchesPublic(SQLModel):
    data: list[ProductionBatchSummary]
    count: int


class FinishedGoodAvailabilityPublic(SQLModel):
    menu_item_id: uuid.UUID
    menu_item_name: str
    inventory_item_id: uuid.UUID
    inventory_item_sku: str
    inventory_item_name: str
    available_quantity: Decimal
    unit: Unit


class FinishedGoodsAvailabilityPublic(SQLModel):
    data: list[FinishedGoodAvailabilityPublic]
