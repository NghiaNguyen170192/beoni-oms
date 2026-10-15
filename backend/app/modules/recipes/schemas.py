import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import field_validator, model_validator
from sqlmodel import Field, SQLModel
from typing_extensions import Self

from app.modules.catalog.models import ProductType
from app.modules.inventory.models import Unit
from app.modules.recipes.models import RecipeKind


class RecipeLineCreate(SQLModel):
    inventory_item_id: uuid.UUID
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)


class RecipeVersionCreate(SQLModel):
    menu_item_id: uuid.UUID
    effective_from: datetime
    lines: list[RecipeLineCreate] = Field(min_length=1, max_length=100)

    @field_validator("effective_from")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("effective_from must include a timezone")
        return value

    @model_validator(mode="after")
    def unique_items(self) -> Self:
        ids = [line.inventory_item_id for line in self.lines]
        if len(set(ids)) != len(ids):
            raise ValueError("Each inventory item can appear only once")
        return self


class RecipeLinePublic(SQLModel):
    id: uuid.UUID
    inventory_item_id: uuid.UUID
    item_sku: str
    item_name: str
    base_unit: Unit
    quantity: Decimal


class RecipePublic(SQLModel):
    id: uuid.UUID
    menu_item_id: uuid.UUID
    menu_item_name: str
    menu_item_code: str
    product_type: ProductType
    version: int
    kind: RecipeKind
    effective_from: datetime
    created_at: datetime
    lines: list[RecipeLinePublic]


class RecipesPublic(SQLModel):
    data: list[RecipePublic]
    count: int


class CostPreviewLinePublic(SQLModel):
    inventory_item_id: uuid.UUID
    item_sku: str
    item_name: str
    base_unit: Unit
    quantity: Decimal
    avg_unit_cost: Decimal
    line_cost: Decimal | None
    cost_unknown: bool


class CostPreviewPublic(SQLModel):
    recipe_id: uuid.UUID
    estimated_cost: Decimal
    lines: list[CostPreviewLinePublic]


class StockReturnLineCreate(SQLModel):
    order_line_id: uuid.UUID
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    sellable: bool


class StockReturnCreate(SQLModel):
    reason: str = Field(min_length=1, max_length=255)
    lines: list[StockReturnLineCreate] = Field(min_length=1, max_length=100)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A reason is required")
        return value

    @model_validator(mode="after")
    def unique_lines(self) -> Self:
        ids = [line.order_line_id for line in self.lines]
        if len(set(ids)) != len(ids):
            raise ValueError("Each order line may appear only once")
        return self


class StockReturnLinePublic(SQLModel):
    id: uuid.UUID
    order_line_id: uuid.UUID
    item_name: str
    quantity: Decimal
    sellable: bool
    unit_cost: Decimal
    movement_id: uuid.UUID | None


class StockReturnPublic(SQLModel):
    id: uuid.UUID
    order_id: uuid.UUID
    reason: str
    created_by_id: uuid.UUID
    created_at: datetime
    lines: list[StockReturnLinePublic]


class StockReturnsPublic(SQLModel):
    data: list[StockReturnPublic]
    count: int
