import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlmodel import Field, SQLModel

from app.modules.accounting.models import AccountKind, ExpensePaymentStatus, RecordStatus


class MoneyAccountPublic(SQLModel):
    id: uuid.UUID
    name: str
    kind: AccountKind
    balance: Decimal
    label: str = "recorded"


class MoneyAccountsPublic(SQLModel):
    data: list[MoneyAccountPublic]
    count: int


class CashMovementPublic(SQLModel):
    id: uuid.UUID
    account_id: uuid.UUID
    amount: Decimal
    occurred_at: datetime
    source_type: str
    source_id: uuid.UUID
    note: str | None


class CashMovementsPublic(SQLModel):
    opening: Decimal
    inflows: Decimal
    outflows: Decimal
    closing: Decimal
    data: list[CashMovementPublic]
    count: int


class CashAdjustmentCreate(SQLModel):
    account_id: uuid.UUID
    amount: Decimal
    reason: str = Field(min_length=1, max_length=255)


class CashAdjustmentPublic(SQLModel):
    id: uuid.UUID
    account_id: uuid.UUID
    amount: Decimal
    reason: str
    status: RecordStatus
    created_at: datetime


class Reversal(SQLModel):
    reason: str = Field(min_length=1, max_length=255)


class ExpenseCategoryCreate(SQLModel):
    name: str = Field(min_length=1, max_length=100)


class ExpenseCategoryPublic(SQLModel):
    id: uuid.UUID
    name: str
    is_active: bool


class ExpenseCreate(SQLModel):
    category_id: uuid.UUID
    amount: Decimal
    expense_date: date
    description: str = Field(min_length=1, max_length=255)
    payment_status: ExpensePaymentStatus
    account_id: uuid.UUID | None = None


class ExpensePay(SQLModel):
    account_id: uuid.UUID
    payment_date: date


class ExpensePublic(SQLModel):
    id: uuid.UUID
    category_id: uuid.UUID
    amount: Decimal
    expense_date: date
    description: str
    payment_status: ExpensePaymentStatus
    account_id: uuid.UUID | None
    paid_at: datetime | None
    status: RecordStatus
    reversal_reason: str | None
    created_at: datetime


class CategoryTotal(SQLModel):
    category_id: uuid.UUID
    category_name: str
    total: Decimal


class ExpensesPublic(SQLModel):
    data: list[ExpensePublic]
    count: int
    totals: list[CategoryTotal]


class AllocationIn(SQLModel):
    payable_id: uuid.UUID
    amount: Decimal


class SupplierPaymentCreate(SQLModel):
    supplier_id: uuid.UUID
    amount: Decimal
    payment_date: date
    account_id: uuid.UUID
    reference: str | None = Field(default=None, max_length=100)
    allocations: list[AllocationIn] = []


class SupplierPaymentPublic(SQLModel):
    id: uuid.UUID
    supplier_id: uuid.UUID
    amount: Decimal
    payment_date: date
    account_id: uuid.UUID
    reference: str | None
    status: RecordStatus


class StatementEntry(SQLModel):
    kind: str
    id: uuid.UUID
    occurred_at: datetime
    reference: str | None
    purchases: Decimal
    payments: Decimal
    outstanding: Decimal


class StatementPublic(SQLModel):
    data: list[StatementEntry]
    count: int


class FinancialSummaryPublic(SQLModel):
    gross_sales: Decimal
    discounts: Decimal
    refunds: Decimal
    tax: Decimal
    net_sales: Decimal
    cogs: Decimal
    gross_profit: Decimal
    expenses: Decimal
    operating_profit: Decimal
    uncertain_cost_lines: int
    missing_cost_lines: int


class IncomeRow(SQLModel):
    order_id: uuid.UUID
    number: str
    completed_at: datetime
    gross_sales: Decimal
    discounts: Decimal
    refunds: Decimal
    tax: Decimal
    net_sales: Decimal
    payment_status: str


class IncomePublic(SQLModel):
    data: list[IncomeRow]
    count: int
