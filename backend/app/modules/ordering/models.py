import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import CheckConstraint, Date, DateTime, Index, Numeric
from sqlmodel import Field, SQLModel

from app.core.db_types import EnumString
from app.models import get_datetime_utc
from app.modules.catalog.models import ProductType
from app.modules.ordering.pricing import DiscountType
from app.modules.ordering.states import OrderStatus


class OrderType(str, Enum):
    COUNTER = "counter"
    TAKEAWAY = "takeaway"
    DINE_IN = "dine_in"


def _sql_values(enum_class: type[Enum]) -> str:
    return ", ".join(f"'{member.value}'" for member in enum_class)


def _money(default: Decimal | None = Decimal("0")) -> Any:
    return Field(default=default, sa_type=Numeric(18, 2))  # type: ignore


def _timestamp() -> Any:
    return Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        nullable=False,
    )


def _optional_timestamp() -> Any:
    return Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore


ORDER_NUMBER_CONSTRAINT = "uq_orders_number"


class OrderNumberCounter(SQLModel, table=True):
    """Last order number issued per business-timezone day."""

    __tablename__ = "order_number_counters"

    business_date: date = Field(sa_type=Date, primary_key=True)
    last_number: int


class Order(SQLModel, table=True):
    __tablename__ = "orders"
    __table_args__ = (
        Index(ORDER_NUMBER_CONSTRAINT, "number", unique=True),
        Index("ix_orders_business_date", "business_date"),
        Index("ix_orders_cashier_created", "cashier_id", "created_at"),
        Index("ix_orders_status", "status"),
        CheckConstraint(
            f"status IN ({_sql_values(OrderStatus)})", name="ck_orders_status"
        ),
        CheckConstraint(
            f"order_type IN ({_sql_values(OrderType)})", name="ck_orders_type"
        ),
        CheckConstraint(
            "order_type = 'dine_in' OR table_label IS NULL",
            name="ck_orders_table_label",
        ),
        CheckConstraint(
            "order_discount_type IS NULL OR order_discount_type IN "
            f"({_sql_values(DiscountType)})",
            name="ck_orders_discount_type",
        ),
        CheckConstraint(
            "subtotal >= 0 AND discount_total >= 0 AND tax_total >= 0 AND total >= 0",
            name="ck_orders_amounts_non_negative",
        ),
        CheckConstraint("total = subtotal - discount_total", name="ck_orders_total"),
        CheckConstraint("tax_rate >= 0 AND tax_rate <= 100", name="ck_orders_tax_rate"),
        CheckConstraint(
            "(status = 'cancelled') = (cancelled_at IS NOT NULL)",
            name="ck_orders_cancelled_at",
        ),
        CheckConstraint(
            "status <> 'cancelled' OR cancel_reason IS NOT NULL",
            name="ck_orders_cancel_reason",
        ),
        CheckConstraint(
            "status NOT IN ('completed', 'partially_refunded', 'refunded') "
            "OR completed_at IS NOT NULL",
            name="ck_orders_completed_at",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    number: str = Field(max_length=32)
    business_date: date = Field(sa_type=Date)
    order_type: OrderType = Field(sa_type=EnumString(OrderType), nullable=False)  # type: ignore
    table_label: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=500)
    status: OrderStatus = Field(
        default=OrderStatus.DRAFT,
        sa_type=EnumString(OrderStatus),  # type: ignore
        nullable=False,
    )
    tax_rate: Decimal = Field(default=Decimal("0"), sa_type=Numeric(5, 2))  # type: ignore
    subtotal: Decimal = _money()
    discount_total: Decimal = _money()
    order_discount_type: DiscountType | None = Field(
        default=None,
        sa_type=EnumString(DiscountType, length=16),  # type: ignore
    )
    order_discount_value: Decimal | None = _money(None)
    order_discount_amount: Decimal = _money()
    order_discount_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    tax_total: Decimal = _money()
    total: Decimal = _money()
    cashier_id: uuid.UUID = Field(foreign_key="user.id", ondelete="RESTRICT")
    created_at: datetime = _timestamp()
    updated_at: datetime = _timestamp()
    confirmed_at: datetime | None = _optional_timestamp()
    completed_at: datetime | None = _optional_timestamp()
    completed_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    cancelled_at: datetime | None = _optional_timestamp()
    cancelled_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    cancel_reason: str | None = Field(default=None, max_length=255)


class OrderLine(SQLModel, table=True):
    """Snapshot of what was sold: name, code, price, and amounts as of when the
    line was added or last changed while the order was open."""

    __tablename__ = "order_lines"
    __table_args__ = (
        Index("ix_order_lines_order_id", "order_id"),
        Index("ix_order_lines_menu_item_id", "menu_item_id"),
        CheckConstraint(
            "quantity > 0 AND quantity = round(quantity, 3)",
            name="ck_order_lines_quantity",
        ),
        CheckConstraint("unit_price >= 0", name="ck_order_lines_unit_price"),
        CheckConstraint(
            f"discount_type IS NULL OR discount_type IN ({_sql_values(DiscountType)})",
            name="ck_order_lines_discount_type",
        ),
        CheckConstraint(
            f"product_type IN ({_sql_values(ProductType)})",
            name="ck_order_lines_product_type",
        ),
        CheckConstraint(
            "discount_amount >= 0 AND line_total >= 0 AND net_total >= 0 "
            "AND order_discount_share >= 0 AND tax_amount >= 0",
            name="ck_order_lines_amounts_non_negative",
        ),
        CheckConstraint(
            "net_total = line_total - order_discount_share", name="ck_order_lines_net"
        ),
        CheckConstraint(
            "cogs_amount IS NULL OR cogs_amount >= 0",
            name="ck_order_lines_cogs_non_negative",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    order_id: uuid.UUID = Field(foreign_key="orders.id", ondelete="RESTRICT")
    line_no: int
    menu_item_id: uuid.UUID = Field(foreign_key="menu_items.id", ondelete="RESTRICT")
    item_code: str = Field(max_length=32)
    item_name: str = Field(max_length=255)
    product_type: ProductType = Field(sa_type=EnumString(ProductType), nullable=False)  # type: ignore
    unit_price: Decimal = _money(None)
    quantity: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore
    note: str | None = Field(default=None, max_length=255)
    discount_type: DiscountType | None = Field(
        default=None,
        sa_type=EnumString(DiscountType, length=16),  # type: ignore
    )
    discount_value: Decimal | None = _money(None)
    discount_amount: Decimal = _money()
    discount_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    line_total: Decimal = _money()
    order_discount_share: Decimal = _money()
    net_total: Decimal = _money()
    tax_rate: Decimal = Field(default=Decimal("0"), sa_type=Numeric(5, 2))  # type: ignore
    tax_amount: Decimal = _money()
    recipe_version_id: uuid.UUID | None = Field(
        default=None, foreign_key="recipes.id", ondelete="RESTRICT"
    )
    cogs_amount: Decimal | None = Field(default=None, sa_type=Numeric(18, 2))  # type: ignore
    cost_uncertain: bool = False
    created_at: datetime = _timestamp()
    updated_at: datetime = _timestamp()
