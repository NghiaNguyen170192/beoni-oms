import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import field_validator
from sqlmodel import Field, SQLModel

from app.modules.payments.models import PaymentMethodKind, PaymentStatus


def _strip(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class PaymentMethodCreate(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    kind: PaymentMethodKind
    is_active: bool = True

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        return _strip(value)


class PaymentMethodUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        return _strip(value)


class PaymentMethodPublic(SQLModel):
    id: uuid.UUID
    name: str
    kind: PaymentMethodKind
    is_active: bool
    created_at: datetime


class PaymentMethodsPublic(SQLModel):
    data: list[PaymentMethodPublic]
    count: int


class PaymentCreate(SQLModel):
    method_id: uuid.UUID
    amount: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    tendered: Decimal | None = Field(
        default=None, gt=0, max_digits=18, decimal_places=2
    )
    reference: str | None = Field(default=None, max_length=100)

    @field_validator("reference", mode="before")
    @classmethod
    def strip_reference(cls, value: str | None) -> str | None:
        return _strip(value)


class PaymentVoid(SQLModel):
    reason: str = Field(min_length=1, max_length=255)

    @field_validator("reason", mode="before")
    @classmethod
    def strip_reason(cls, value: str | None) -> str | None:
        return _strip(value)


class RefundLineIn(SQLModel):
    order_line_id: uuid.UUID
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)


class RefundCreate(SQLModel):
    method_id: uuid.UUID
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    reason: str = Field(min_length=1, max_length=255)
    reference: str | None = Field(default=None, max_length=100)
    lines: list[RefundLineIn] = Field(default_factory=list, max_length=100)

    @field_validator("reason", "reference", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return _strip(value)


class PaymentPublic(SQLModel):
    id: uuid.UUID
    order_id: uuid.UUID
    order_number: str
    method_id: uuid.UUID
    method_name: str
    method_kind: PaymentMethodKind
    amount: Decimal
    tendered: Decimal | None
    change_amount: Decimal | None
    reference: str | None
    status: PaymentStatus
    void_reason: str | None
    recorded_by_id: uuid.UUID
    recorded_at: datetime
    voided_at: datetime | None


class RefundLinePublic(SQLModel):
    id: uuid.UUID
    order_line_id: uuid.UUID
    quantity: Decimal
    amount: Decimal


class RefundPublic(SQLModel):
    id: uuid.UUID
    order_id: uuid.UUID
    order_number: str
    method_id: uuid.UUID
    method_name: str
    method_kind: PaymentMethodKind
    amount: Decimal
    reason: str
    reference: str | None
    recorded_by_id: uuid.UUID
    recorded_at: datetime
    lines: list[RefundLinePublic] = []


class MethodTotal(SQLModel):
    method_id: uuid.UUID
    method_name: str
    method_kind: PaymentMethodKind
    total: Decimal


class PaymentsPublic(SQLModel):
    data: list[PaymentPublic]
    count: int
    totals: list[MethodTotal]


class RefundsPublic(SQLModel):
    data: list[RefundPublic]
    count: int
    totals: list[MethodTotal]


class OrderPaymentSummary(SQLModel):
    order_id: uuid.UUID
    order_total: Decimal
    paid_amount: Decimal
    refunded_amount: Decimal
    remaining: Decimal
    payments: list[PaymentPublic]
