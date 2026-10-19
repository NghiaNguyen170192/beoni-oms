import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import Field
from sqlmodel import SQLModel

from app.modules.inventory.models import ItemType, MovementType
from app.modules.production.models import ProductionBatchStatus
from app.modules.reporting.periods import GroupBy


class ResolvedPeriod(SQLModel):
    preset: str
    date_from: date
    date_to: date


class DashboardSales(SQLModel):
    date_from: date
    date_to: date
    net_sales: Decimal
    order_count: int
    average_order_value: Decimal
    discounts: Decimal
    refunds: Decimal
    low_stock_count: int


class DashboardFinancial(DashboardSales):
    cogs: Decimal
    gross_profit: Decimal
    expenses: Decimal
    operating_profit: Decimal


class SalesSummaryRow(SQLModel):
    period_start: date
    gross_sales: Decimal
    discounts: Decimal
    refunds: Decimal
    net_sales: Decimal
    order_count: int
    average_order_value: Decimal


class PaymentBreakdownRow(SQLModel):
    method_id: uuid.UUID
    method_name: str
    amount: Decimal


class SalesSummaryPublic(SQLModel):
    date_from: date
    date_to: date
    group_by: GroupBy
    gross_sales: Decimal
    discounts: Decimal
    refunds: Decimal
    net_sales: Decimal
    order_count: int
    average_order_value: Decimal
    data: list[SalesSummaryRow]
    payments: list[PaymentBreakdownRow]


class ProductRow(SQLModel):
    menu_item_id: uuid.UUID
    name: str
    quantity: Decimal
    gross_sales: Decimal
    discounts: Decimal
    net_sales: Decimal
    share: Decimal
    best_seller: bool = False
    least_seller: bool = False


class ProductRowFinancial(ProductRow):
    estimated_cost: Decimal
    estimated_gross_profit: Decimal


class ProductPerformancePublic(SQLModel):
    date_from: date
    date_to: date
    net_sales: Decimal
    data: list[ProductRow]


class ProductPerformanceFinancial(SQLModel):
    date_from: date
    date_to: date
    net_sales: Decimal
    data: list[ProductRowFinancial]


class LotMovementRow(SQLModel):
    id: uuid.UUID
    lot_id: uuid.UUID
    lot_number: str
    batch_number: int | None
    movement_type: MovementType
    quantity: Decimal
    occurred_at: datetime


class MovementRow(SQLModel):
    item_id: uuid.UUID
    sku: str
    name: str
    base_unit: str
    opening: Decimal
    received: Decimal
    production_received: Decimal
    consumed: Decimal
    production_consumed: Decimal
    adjustments: Decimal
    spoilage: Decimal
    expired: Decimal
    damaged: Decimal
    missing: Decimal
    physical_count: Decimal
    correction: Decimal
    returns: Decimal
    reversals: Decimal
    closing: Decimal
    closing_value: Decimal
    lot_movements: list[LotMovementRow] = Field(default_factory=list)


class MovementReportPublic(SQLModel):
    date_from: date
    date_to: date
    data: list[MovementRow]
    count: int


class StockStatusItem(SQLModel):
    item_id: uuid.UUID
    sku: str
    name: str
    item_type: ItemType
    quantity: Decimal
    base_unit: str
    value: Decimal


class StockStatusPublic(SQLModel):
    total_value: Decimal
    items: list[StockStatusItem]
    low_stock: list[StockStatusItem]
    negative_stock: list[StockStatusItem]


class ExpenseBreakdownRow(SQLModel):
    category_id: uuid.UUID | None
    category_name: str
    amount: Decimal
    share: Decimal


class ExpenseBreakdownPublic(SQLModel):
    date_from: date
    date_to: date
    total: Decimal
    data: list[ExpenseBreakdownRow]


class ProductionReportRow(SQLModel):
    batch_id: uuid.UUID
    batch_number: int
    status: ProductionBatchStatus
    report_date: date
    menu_item_id: uuid.UUID
    menu_item_name: str
    planned_quantity: Decimal
    actual_good_quantity: Decimal | None
    waste_quantity: Decimal


class ProductionReportPublic(SQLModel):
    date_from: date
    date_to: date
    data: list[ProductionReportRow]
    count: int


class ProfitStatementPublic(SQLModel):
    date_from: date
    date_to: date
    net_sales: Decimal
    cogs: Decimal
    gross_profit: Decimal
    gross_margin: Decimal
    expenses: Decimal
    operating_profit: Decimal
    estimate: bool = True
    note: str = "Management estimate, not statutory accounts"
    uncertain_cost_lines: int
    missing_cost_lines: int


class ComparisonLine(SQLModel):
    key: str
    current: Decimal
    previous: Decimal
    change: Decimal
    change_percent: Decimal | None


class ProfitComparisonPublic(SQLModel):
    date_from: date
    date_to: date
    compare_from: date
    compare_to: date
    lines: list[ComparisonLine]
    note: str = "Management estimate, not statutory accounts"
    uncertain_cost_lines: int = 0
    missing_cost_lines: int = 0


class SalesQuery(SQLModel):
    date_from: date
    date_to: date
    group_by: GroupBy = GroupBy.DAY
    cashier_id: uuid.UUID | None = None
    method_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    status: str | None = None
    sort: str = Field(default="quantity")
