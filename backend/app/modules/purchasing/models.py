import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import CheckConstraint, Date, DateTime, Index, Numeric
from sqlmodel import Field, SQLModel

from app.core.db_types import EnumString
from app.models import get_datetime_utc


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


class ReceiptStatus(str, Enum):
    DRAFT = "draft"
    POSTED = "posted"
    REVERSED = "reversed"


class PayableStatus(str, Enum):
    UNPAID = "unpaid"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    CANCELLED = "cancelled"


class ReceiptPaymentStatus(str, Enum):
    UNPAID = "unpaid"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"


SUPPLIER_CODE_INDEX = "uq_suppliers_code"
RECEIPT_REFERENCE_INDEX = "uq_stock_receipts_reference"
PAYABLE_RECEIPT_INDEX = "uq_supplier_payables_receipt"


class Supplier(SQLModel, table=True):
    __tablename__ = "suppliers"
    __table_args__ = (Index(SUPPLIER_CODE_INDEX, "code", unique=True),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=255)
    code: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    tax_code: str | None = Field(default=None, max_length=32)
    contact_person: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=1000)
    is_active: bool = True
    created_at: datetime = _timestamp()
    updated_at: datetime = _timestamp()


class ReceiptReferenceCounter(SQLModel, table=True):
    """Last receipt reference issued per business-timezone day."""

    __tablename__ = "receipt_reference_counters"

    business_date: date = Field(sa_type=Date, primary_key=True)
    last_number: int


class StockReceipt(SQLModel, table=True):
    __tablename__ = "stock_receipts"
    __table_args__ = (
        Index(RECEIPT_REFERENCE_INDEX, "reference", unique=True),
        Index("ix_stock_receipts_supplier", "supplier_id"),
        Index("ix_stock_receipts_date", "receipt_date"),
        CheckConstraint(
            f"status IN ({_sql_values(ReceiptStatus)})",
            name="ck_stock_receipts_status",
        ),
        CheckConstraint(
            "(status = 'draft') = (posted_at IS NULL)",
            name="ck_stock_receipts_posted_at",
        ),
        CheckConstraint(
            "(status = 'reversed') = (reversed_by_id IS NOT NULL)",
            name="ck_stock_receipts_reversed_by",
        ),
        CheckConstraint(
            "reversal_of_id IS NULL OR status = 'posted'",
            name="ck_stock_receipts_reversal_posted",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    reference: str = Field(max_length=64)
    supplier_id: uuid.UUID = Field(foreign_key="suppliers.id", ondelete="RESTRICT")
    receipt_date: date = Field(sa_type=Date)
    notes: str | None = Field(default=None, max_length=1000)
    status: ReceiptStatus = Field(
        default=ReceiptStatus.DRAFT,
        sa_type=EnumString(ReceiptStatus),  # type: ignore
        nullable=False,
    )
    total_value: Decimal = Field(default=Decimal("0"), sa_type=Numeric(18, 2))  # type: ignore
    created_by_id: uuid.UUID = Field(foreign_key="user.id", ondelete="RESTRICT")
    created_at: datetime = _timestamp()
    updated_at: datetime = _timestamp()
    posted_at: datetime | None = _optional_timestamp()
    posted_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    reversed_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="stock_receipts.id", ondelete="RESTRICT"
    )
    reversal_of_id: uuid.UUID | None = Field(
        default=None, foreign_key="stock_receipts.id", ondelete="RESTRICT"
    )
    reversal_reason: str | None = Field(default=None, max_length=500)


class StockReceiptLine(SQLModel, table=True):
    __tablename__ = "stock_receipt_lines"
    __table_args__ = (
        Index("ix_stock_receipt_lines_receipt", "receipt_id"),
        CheckConstraint(
            "purchase_qty <> 0", name="ck_stock_receipt_lines_qty_nonzero"
        ),
        CheckConstraint(
            "purchase_unit_cost >= 0", name="ck_stock_receipt_lines_cost"
        ),
        CheckConstraint("base_qty <> 0", name="ck_stock_receipt_lines_base_qty"),
        CheckConstraint(
            "base_unit_cost >= 0", name="ck_stock_receipt_lines_base_cost"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    receipt_id: uuid.UUID = Field(
        foreign_key="stock_receipts.id", ondelete="CASCADE"
    )
    line_no: int
    item_id: uuid.UUID = Field(foreign_key="inventory_items.id", ondelete="RESTRICT")
    purchase_qty: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore
    purchase_unit_cost: Decimal = Field(sa_type=Numeric(18, 2))  # type: ignore
    base_qty: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore
    base_unit_cost: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore
    line_total: Decimal = Field(sa_type=Numeric(18, 2))  # type: ignore


class SupplierPayable(SQLModel, table=True):
    __tablename__ = "supplier_payables"
    __table_args__ = (
        Index(PAYABLE_RECEIPT_INDEX, "receipt_id", unique=True),
        Index("ix_supplier_payables_supplier", "supplier_id"),
        CheckConstraint(
            f"status IN ({_sql_values(PayableStatus)})",
            name="ck_supplier_payables_status",
        ),
        CheckConstraint("amount >= 0", name="ck_supplier_payables_amount"),
        CheckConstraint(
            "paid_amount >= 0 AND paid_amount <= amount",
            name="ck_supplier_payables_paid",
        ),
        CheckConstraint(
            "(status = 'cancelled') "
            "OR (status = 'unpaid' AND paid_amount = 0) "
            "OR (status = 'partially_paid' AND paid_amount > 0 AND paid_amount < amount) "
            "OR (status = 'paid' AND paid_amount = amount AND amount > 0) "
            "OR (status = 'unpaid' AND amount = 0 AND paid_amount = 0)",
            name="ck_supplier_payables_status_amounts",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    receipt_id: uuid.UUID = Field(
        foreign_key="stock_receipts.id", ondelete="RESTRICT"
    )
    supplier_id: uuid.UUID = Field(foreign_key="suppliers.id", ondelete="RESTRICT")
    amount: Decimal = Field(sa_type=Numeric(18, 2))  # type: ignore
    paid_amount: Decimal = Field(default=Decimal("0"), sa_type=Numeric(18, 2))  # type: ignore
    status: PayableStatus = Field(
        default=PayableStatus.UNPAID,
        sa_type=EnumString(PayableStatus),  # type: ignore
        nullable=False,
    )
