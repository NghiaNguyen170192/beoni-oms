import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import field_validator, model_validator
from sqlmodel import Field, SQLModel
from typing_extensions import Self

from app.modules.catalog.models import ProductType
from app.modules.ordering.models import OrderType
from app.modules.ordering.pricing import DiscountType
from app.modules.ordering.states import OrderStatus

MAX_ORDER_LINES = 100
QUANTITY_STEP = Decimal("0.001")


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


class OrderLineInput(SQLModel):
    """A cart line. Send `id` to keep an existing line (and its snapshot when
    unchanged); omit it to add a new line. Lines not sent are removed."""

    id: uuid.UUID | None = None
    menu_item_id: uuid.UUID
    quantity: Decimal = Field(gt=0, max_digits=15, decimal_places=3)
    note: str | None = Field(default=None, max_length=255)

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class OrderLinesReplace(SQLModel):
    lines: list[OrderLineInput] = Field(max_length=MAX_ORDER_LINES)

    @model_validator(mode="after")
    def unique_line_ids(self) -> Self:
        ids = [line.id for line in self.lines if line.id is not None]
        if len(set(ids)) != len(ids):
            raise ValueError("Each existing line may appear only once")
        return self


class OrderHeaderFields(SQLModel):
    @model_validator(mode="after")
    def table_only_for_dine_in(self) -> Self:
        order_type = getattr(self, "order_type", None)
        table_label = getattr(self, "table_label", None)
        if table_label and order_type is not None and order_type != OrderType.DINE_IN:
            raise ValueError("Only dine-in orders have a table label")
        return self


class OrderCreate(OrderHeaderFields):
    order_type: OrderType
    table_label: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=500)
    lines: list[OrderLineInput] = Field(
        default_factory=list, max_length=MAX_ORDER_LINES
    )

    @field_validator("table_label", "notes")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class OrderUpdate(OrderHeaderFields):
    order_type: OrderType | None = None
    table_label: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("table_label", "notes")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class DiscountUpdate(SQLModel):
    """`discount_type: null` removes the discount."""

    discount_type: DiscountType | None
    discount_value: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=2
    )

    @model_validator(mode="after")
    def check_value(self) -> Self:
        if self.discount_type is None:
            self.discount_value = None
            return self
        if self.discount_value is None:
            raise ValueError("discount_value is required")
        if self.discount_type == DiscountType.PERCENT and self.discount_value > 100:
            raise ValueError("Percentage discount must be between 0 and 100")
        return self


class OrderCancel(SQLModel):
    reason: str = Field(min_length=1, max_length=255)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A cancellation reason is required")
        return value


class OrderLinePublic(SQLModel):
    id: uuid.UUID
    line_no: int
    menu_item_id: uuid.UUID
    item_code: str
    item_name: str
    product_type: ProductType
    unit_price: Decimal
    quantity: Decimal
    note: str | None
    discount_type: DiscountType | None
    discount_value: Decimal | None
    discount_amount: Decimal
    discount_by_id: uuid.UUID | None
    line_total: Decimal
    order_discount_share: Decimal
    net_total: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    recipe_version_id: uuid.UUID | None = None
    cogs_amount: Decimal | None = None
    cost_uncertain: bool = False


class OrderPublic(SQLModel):
    id: uuid.UUID
    number: str
    business_date: date
    order_type: OrderType
    table_label: str | None
    notes: str | None
    status: OrderStatus
    tax_rate: Decimal
    subtotal: Decimal
    discount_total: Decimal
    order_discount_type: DiscountType | None
    order_discount_value: Decimal | None
    order_discount_amount: Decimal
    order_discount_by_id: uuid.UUID | None
    tax_total: Decimal
    total: Decimal
    cashier_id: uuid.UUID
    cashier_email: str | None
    cashier_name: str | None
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None
    completed_at: datetime | None
    completed_by_id: uuid.UUID | None
    cancelled_at: datetime | None
    cancelled_by_id: uuid.UUID | None
    cancel_reason: str | None
    lines: list[OrderLinePublic]


class OrderSummary(SQLModel):
    id: uuid.UUID
    number: str
    business_date: date
    order_type: OrderType
    table_label: str | None
    status: OrderStatus
    total: Decimal
    cashier_id: uuid.UUID
    cashier_email: str | None
    cashier_name: str | None
    created_at: datetime
    completed_at: datetime | None


class OrdersPublic(SQLModel):
    data: list[OrderSummary]
    count: int


class ReceiptPublic(SQLModel):
    business_name: str
    currency_code: str
    timezone: str
    order: OrderPublic
