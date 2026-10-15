import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import field_validator
from sqlmodel import Field, SQLModel

from app.core.money import optional_money as money
from app.modules.catalog.models import ProductType

MAX_IMAGE_BYTES = 2 * 1024 * 1024


def strip_required(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError("Must not be blank")
    return value


def strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


# Categories


class MenuCategoryCreate(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = Field(default=0, ge=0)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str | None:
        return strip_required(value)


class MenuCategoryUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return strip_required(value)


class MenuCategoriesReorder(SQLModel):
    category_ids: list[uuid.UUID] = Field(min_length=1)


class MenuCategoryPublic(SQLModel):
    id: uuid.UUID
    name: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MenuCategoriesPublic(SQLModel):
    data: list[MenuCategoryPublic]
    count: int


# Items


class MenuItemCreate(SQLModel):
    """The product code is assigned by the system."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    category_id: uuid.UUID
    price: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    product_type: ProductType
    is_active: bool = True
    is_available: bool = True

    @field_validator("price")
    @classmethod
    def scale_price(cls, value: Decimal) -> Decimal | None:
        return money(value)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str | None:
        return strip_required(value)

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        return strip_optional(value)


class MenuItemUpdate(SQLModel):
    """The product code never changes."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    category_id: uuid.UUID | None = None
    price: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    product_type: ProductType | None = None
    is_active: bool | None = None
    is_available: bool | None = None

    @field_validator("price")
    @classmethod
    def scale_price(cls, value: Decimal | None) -> Decimal | None:
        return money(value)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return strip_required(value)

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        return strip_optional(value)


class MenuItemPublic(SQLModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    category_id: uuid.UUID
    price: Decimal
    product_type: ProductType
    is_active: bool
    is_available: bool
    image_path: str | None
    created_at: datetime
    updated_at: datetime


class MenuItemsPublic(SQLModel):
    data: list[MenuItemPublic]
    count: int
