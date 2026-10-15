import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import CheckConstraint, Date, DateTime, Index, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.db_types import EnumString
from app.models import get_datetime_utc


class AccountKind(str, Enum):
    CASH = "cash"
    BANK = "bank"


class ExpensePaymentStatus(str, Enum):
    PAID = "paid"
    UNPAID = "unpaid"


class RecordStatus(str, Enum):
    RECORDED = "recorded"
    REVERSED = "reversed"


def _sql_values(enum_class: type[Enum]) -> str:
    return ", ".join(f"'{member.value}'" for member in enum_class)


def _timestamp() -> Any:
    return Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        nullable=False,
    )


class MoneyAccount(SQLModel, table=True):
    __tablename__ = "money_accounts"
    __table_args__ = (
        UniqueConstraint("name", name="uq_money_accounts_name"),
        CheckConstraint(
            f"kind IN ({_sql_values(AccountKind)})", name="ck_money_accounts_kind"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=100)
    kind: AccountKind = Field(sa_type=EnumString(AccountKind), nullable=False)  # type: ignore
    is_active: bool = True
    created_at: datetime = _timestamp()


class CashMovement(SQLModel, table=True):
    """Signed money movement. Inflows are positive, outflows negative."""

    __tablename__ = "cash_movements"
    __table_args__ = (
        UniqueConstraint(
            "source_type", "source_id", name="uq_cash_movements_source"
        ),
        Index("ix_cash_movements_account_time", "account_id", "occurred_at"),
        CheckConstraint("amount <> 0", name="ck_cash_movements_amount"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    account_id: uuid.UUID = Field(foreign_key="money_accounts.id", ondelete="RESTRICT")
    amount: Decimal = Field(sa_type=Numeric(18, 2))  # type: ignore
    occurred_at: datetime = Field(sa_type=DateTime(timezone=True), nullable=False)  # type: ignore
    source_type: str = Field(max_length=64)
    source_id: uuid.UUID
    actor_id: uuid.UUID = Field(foreign_key="user.id", ondelete="RESTRICT")
    note: str | None = Field(default=None, max_length=255)


class CashAdjustment(SQLModel, table=True):
    __tablename__ = "cash_adjustments"
    __table_args__ = (
        CheckConstraint("amount <> 0", name="ck_cash_adjustments_amount"),
        CheckConstraint(
            f"status IN ({_sql_values(RecordStatus)})",
            name="ck_cash_adjustments_status",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    account_id: uuid.UUID = Field(foreign_key="money_accounts.id", ondelete="RESTRICT")
    amount: Decimal = Field(sa_type=Numeric(18, 2))  # type: ignore
    reason: str = Field(max_length=255)
    status: RecordStatus = Field(
        default=RecordStatus.RECORDED,
        sa_type=EnumString(RecordStatus),  # type: ignore
        nullable=False,
    )
    reversal_of_id: uuid.UUID | None = Field(
        default=None, foreign_key="cash_adjustments.id", ondelete="RESTRICT"
    )
    recorded_by_id: uuid.UUID = Field(foreign_key="user.id", ondelete="RESTRICT")
    created_at: datetime = _timestamp()


class ExpenseCategory(SQLModel, table=True):
    __tablename__ = "expense_categories"
    __table_args__ = (
        UniqueConstraint("name", name="uq_expense_categories_name"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=100)
    is_active: bool = True
    created_at: datetime = _timestamp()


class Expense(SQLModel, table=True):
    __tablename__ = "expenses"
    __table_args__ = (
        Index("ix_expenses_date", "expense_date"),
        CheckConstraint("amount > 0", name="ck_expenses_amount"),
        CheckConstraint(
            f"payment_status IN ({_sql_values(ExpensePaymentStatus)})",
            name="ck_expenses_payment_status",
        ),
        CheckConstraint(
            f"status IN ({_sql_values(RecordStatus)})", name="ck_expenses_status"
        ),
        CheckConstraint(
            "(payment_status = 'paid') = (account_id IS NOT NULL AND paid_at IS NOT NULL)",
            name="ck_expenses_paid",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    category_id: uuid.UUID = Field(
        foreign_key="expense_categories.id", ondelete="RESTRICT"
    )
    amount: Decimal = Field(sa_type=Numeric(18, 2))  # type: ignore
    expense_date: date = Field(sa_type=Date)
    description: str = Field(max_length=255)
    payment_status: ExpensePaymentStatus = Field(
        sa_type=EnumString(ExpensePaymentStatus),  # type: ignore
        nullable=False,
    )
    account_id: uuid.UUID | None = Field(
        default=None, foreign_key="money_accounts.id", ondelete="RESTRICT"
    )
    paid_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)  # type: ignore
    )
    status: RecordStatus = Field(
        default=RecordStatus.RECORDED,
        sa_type=EnumString(RecordStatus),  # type: ignore
        nullable=False,
    )
    reversal_reason: str | None = Field(default=None, max_length=255)
    recorded_by_id: uuid.UUID = Field(foreign_key="user.id", ondelete="RESTRICT")
    created_at: datetime = _timestamp()


class SupplierPayment(SQLModel, table=True):
    __tablename__ = "supplier_payments"
    __table_args__ = (
        Index("ix_supplier_payments_supplier", "supplier_id"),
        CheckConstraint("amount > 0", name="ck_supplier_payments_amount"),
        CheckConstraint(
            f"status IN ({_sql_values(RecordStatus)})",
            name="ck_supplier_payments_status",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    supplier_id: uuid.UUID = Field(foreign_key="suppliers.id", ondelete="RESTRICT")
    amount: Decimal = Field(sa_type=Numeric(18, 2))  # type: ignore
    payment_date: date = Field(sa_type=Date)
    account_id: uuid.UUID = Field(foreign_key="money_accounts.id", ondelete="RESTRICT")
    reference: str | None = Field(default=None, max_length=100)
    status: RecordStatus = Field(
        default=RecordStatus.RECORDED,
        sa_type=EnumString(RecordStatus),  # type: ignore
        nullable=False,
    )
    reversal_reason: str | None = Field(default=None, max_length=255)
    recorded_by_id: uuid.UUID = Field(foreign_key="user.id", ondelete="RESTRICT")
    created_at: datetime = _timestamp()


class SupplierPaymentAllocation(SQLModel, table=True):
    __tablename__ = "supplier_payment_allocations"
    __table_args__ = (
        UniqueConstraint(
            "payment_id", "payable_id", name="uq_supplier_payment_allocations"
        ),
        CheckConstraint("amount > 0", name="ck_supplier_payment_allocations_amount"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    payment_id: uuid.UUID = Field(
        foreign_key="supplier_payments.id", ondelete="RESTRICT"
    )
    payable_id: uuid.UUID = Field(
        foreign_key="supplier_payables.id", ondelete="RESTRICT"
    )
    amount: Decimal = Field(sa_type=Numeric(18, 2))  # type: ignore
