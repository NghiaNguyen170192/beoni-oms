import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import field_validator
from sqlmodel import Field, SQLModel

from app.modules.purchasing.models import (
    PayableStatus,
    ReceiptPaymentStatus,
    ReceiptStatus,
)


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


class SupplierCreate(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    tax_code: str | None = Field(default=None, max_length=32)
    contact_person: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=1000)
    is_active: bool = True

    @field_validator(
        "name",
        "code",
        "phone",
        "email",
        "address",
        "tax_code",
        "contact_person",
        "notes",
        mode="before",
    )
    @classmethod
    def strip(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("name")
    @classmethod
    def name_required(cls, value: str | None) -> str:
        if not value:
            raise ValueError("Must not be blank")
        return value


class SupplierUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    tax_code: str | None = Field(default=None, max_length=32)
    contact_person: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None

    @field_validator(
        "name",
        "code",
        "phone",
        "email",
        "address",
        "tax_code",
        "contact_person",
        "notes",
        mode="before",
    )
    @classmethod
    def strip(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class SupplierBalance(SQLModel):
    supplier_id: uuid.UUID
    payables_total: Decimal
    paid_total: Decimal
    outstanding: Decimal


class SupplierPublic(SQLModel):
    id: uuid.UUID
    name: str
    code: str | None
    phone: str | None
    email: str | None
    address: str | None
    tax_code: str | None
    contact_person: str | None
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    payables_total: Decimal
    paid_total: Decimal
    outstanding: Decimal


class SuppliersPublic(SQLModel):
    data: list[SupplierPublic]
    count: int


class ReceiptLineIn(SQLModel):
    item_id: uuid.UUID
    purchase_quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    purchase_unit_cost: Decimal = Field(ge=0, max_digits=18, decimal_places=2)


class ReceiptCreate(SQLModel):
    reference: str | None = Field(default=None, max_length=64)
    supplier_id: uuid.UUID
    receipt_date: date
    notes: str | None = Field(default=None, max_length=1000)
    lines: list[ReceiptLineIn] = Field(min_length=1, max_length=200)
    total: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)

    @field_validator("reference", "notes", mode="before")
    @classmethod
    def strip(cls, value: str | None) -> str | None:
        return _strip_optional(value) if isinstance(value, str) or value is None else value


class ReceiptUpdate(SQLModel):
    reference: str | None = Field(default=None, max_length=64)
    supplier_id: uuid.UUID | None = None
    receipt_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)
    lines: list[ReceiptLineIn] | None = Field(default=None, min_length=1, max_length=200)
    total: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)

    @field_validator("reference", "notes", mode="before")
    @classmethod
    def strip(cls, value: str | None) -> str | None:
        return _strip_optional(value) if isinstance(value, str) or value is None else value


class ReceiptReverse(SQLModel):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def strip_reason(cls, value: str | None) -> str | None:
        return _strip_required(value)


class ReceiptLinePublic(SQLModel):
    id: uuid.UUID
    line_no: int
    item_id: uuid.UUID
    item_sku: str
    item_name: str
    purchase_unit: str
    base_unit: str
    purchase_qty: Decimal
    purchase_unit_cost: Decimal
    base_qty: Decimal
    base_unit_cost: Decimal
    line_total: Decimal


class ReceiptPost(SQLModel):
    payment_amount: Decimal | None = None
    account_id: uuid.UUID | None = None


class StockReceiptPublic(SQLModel):
    id: uuid.UUID
    reference: str
    supplier_id: uuid.UUID
    supplier_name: str
    receipt_date: date
    notes: str | None
    status: ReceiptStatus
    payment_status: ReceiptPaymentStatus
    total_value: Decimal
    created_by_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    posted_at: datetime | None
    posted_by_id: uuid.UUID | None
    reversed_by_id: uuid.UUID | None
    reversal_of_id: uuid.UUID | None
    reversal_reason: str | None
    lines: list[ReceiptLinePublic]


class ReceiptSummary(SQLModel):
    id: uuid.UUID
    reference: str
    supplier_id: uuid.UUID
    supplier_name: str
    receipt_date: date
    status: ReceiptStatus
    payment_status: ReceiptPaymentStatus
    total_value: Decimal
    posted_at: datetime | None


class ReceiptsPublic(SQLModel):
    data: list[ReceiptSummary]
    count: int


class PayablePublic(SQLModel):
    id: uuid.UUID
    receipt_id: uuid.UUID
    supplier_id: uuid.UUID
    amount: Decimal
    paid_amount: Decimal
    status: PayableStatus
