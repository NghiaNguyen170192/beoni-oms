import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, Sequence, text
from sqlmodel import Field, SQLModel

from app.core.db_types import EnumString
from app.models import get_datetime_utc


class ProductType(str, Enum):
    PREPARED = "prepared"
    DIRECT_SALE = "direct_sale"
    NON_STOCK = "non_stock"


PRODUCT_TYPE_VALUES_SQL = ", ".join(f"'{t.value}'" for t in ProductType)

CATEGORY_ACTIVE_NAME_INDEX = "uq_menu_categories_active_name"
ITEM_CODE_CONSTRAINT = "uq_menu_items_code"
ITEM_CODE_PREFIX = "MENU-"
# Created by migration; standalone so autogenerate leaves it alone.
ITEM_CODE_SEQUENCE = Sequence("menu_item_code_seq")


class MenuCategory(SQLModel, table=True):
    __tablename__ = "menu_categories"
    __table_args__ = (
        Index(
            CATEGORY_ACTIVE_NAME_INDEX,
            text("lower(name)"),
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=100)
    sort_order: int = 0
    is_active: bool = True
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        nullable=False,
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        nullable=False,
    )


class MenuItem(SQLModel, table=True):
    __tablename__ = "menu_items"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_menu_items_price_non_negative"),
        CheckConstraint(
            f"product_type IN ({PRODUCT_TYPE_VALUES_SQL})",
            name="ck_menu_items_product_type",
        ),
        CheckConstraint(
            f"code ~ '^{ITEM_CODE_PREFIX}[0-9]{{5,}}$'",
            name="ck_menu_items_code_format",
        ),
        Index(ITEM_CODE_CONSTRAINT, "code", unique=True),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(max_length=32)
    name: str = Field(max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    category_id: uuid.UUID = Field(
        foreign_key="menu_categories.id", ondelete="RESTRICT", index=True
    )
    price: Decimal = Field(sa_type=Numeric(18, 2))  # type: ignore
    product_type: ProductType = Field(
        sa_type=EnumString(ProductType),  # type: ignore
        nullable=False,
    )
    is_active: bool = True
    is_available: bool = True
    image_path: str | None = Field(default=None, max_length=255)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        nullable=False,
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        nullable=False,
    )
