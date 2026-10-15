import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric
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


class PaymentMethodKind(str, Enum):
    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    OTHER = "other"


class PaymentStatus(str, Enum):
    ACTIVE = "active"
    VOIDED = "voided"


METHOD_NAME_INDEX = "uq_payment_methods_name"


class PaymentMethod(SQLModel, table=True):
    __tablename__ = "payment_methods"
    __table_args__ = (
        Index(METHOD_NAME_INDEX, "name", unique=True),
        CheckConstraint(
            f"kind IN ({_sql_values(PaymentMethodKind)})",
            name="ck_payment_methods_kind",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=100)
    kind: PaymentMethodKind = Field(
        sa_type=EnumString(PaymentMethodKind),  # type: ignore
        nullable=False,
    )
    is_active: bool = True
    account_id: uuid.UUID = Field(foreign_key="money_accounts.id", ondelete="RESTRICT")
    created_at: datetime = _timestamp()


class Payment(SQLModel, table=True):
    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_order", "order_id"),
        Index("ix_payments_recorded_at", "recorded_at"),
        CheckConstraint("amount > 0", name="ck_payments_amount"),
        CheckConstraint(
            f"status IN ({_sql_values(PaymentStatus)})", name="ck_payments_status"
        ),
        CheckConstraint(
            "(status = 'voided') = (voided_at IS NOT NULL)",
            name="ck_payments_voided_at",
        ),
        CheckConstraint(
            "tendered IS NULL OR (tendered >= amount AND change_amount = tendered - amount)",
            name="ck_payments_tender",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    order_id: uuid.UUID = Field(foreign_key="orders.id", ondelete="RESTRICT")
    method_id: uuid.UUID = Field(foreign_key="payment_methods.id", ondelete="RESTRICT")
    amount: Decimal = Field(sa_type=Numeric(18, 2))  # type: ignore
    tendered: Decimal | None = Field(default=None, sa_type=Numeric(18, 2))  # type: ignore
    change_amount: Decimal | None = Field(default=None, sa_type=Numeric(18, 2))  # type: ignore
    reference: str | None = Field(default=None, max_length=100)
    status: PaymentStatus = Field(
        default=PaymentStatus.ACTIVE,
        sa_type=EnumString(PaymentStatus),  # type: ignore
        nullable=False,
    )
    void_reason: str | None = Field(default=None, max_length=255)
    recorded_by_id: uuid.UUID = Field(foreign_key="user.id", ondelete="RESTRICT")
    recorded_at: datetime = _timestamp()
    voided_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    voided_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)  # type: ignore
    )


class Refund(SQLModel, table=True):
    __tablename__ = "refunds"
    __table_args__ = (
        Index("ix_refunds_order", "order_id"),
        Index("ix_refunds_recorded_at", "recorded_at"),
        CheckConstraint("amount > 0", name="ck_refunds_amount"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    order_id: uuid.UUID = Field(foreign_key="orders.id", ondelete="RESTRICT")
    method_id: uuid.UUID = Field(foreign_key="payment_methods.id", ondelete="RESTRICT")
    amount: Decimal = Field(sa_type=Numeric(18, 2))  # type: ignore
    reason: str = Field(max_length=255)
    reference: str | None = Field(default=None, max_length=100)
    recorded_by_id: uuid.UUID = Field(foreign_key="user.id", ondelete="RESTRICT")
    recorded_at: datetime = _timestamp()


class RefundLine(SQLModel, table=True):
    __tablename__ = "refund_lines"
    __table_args__ = (
        Index("ix_refund_lines_refund", "refund_id"),
        CheckConstraint("quantity > 0", name="ck_refund_lines_quantity"),
        CheckConstraint("amount >= 0", name="ck_refund_lines_amount"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    refund_id: uuid.UUID = Field(foreign_key="refunds.id", ondelete="CASCADE")
    order_line_id: uuid.UUID = Field(foreign_key="order_lines.id", ondelete="RESTRICT")
    quantity: Decimal = Field(sa_type=Numeric(18, 4))  # type: ignore
    amount: Decimal = Field(sa_type=Numeric(18, 2))  # type: ignore
