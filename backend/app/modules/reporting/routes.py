import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, SessionDep
from app.models import User
from app.modules.accounting.service import income_listing
from app.modules.identity.dependencies import require_permission
from app.modules.identity.permissions import Permission, has_permission
from app.modules.payments.models import PaymentStatus
from app.modules.payments.service import list_payments
from app.modules.reporting import service
from app.modules.reporting.csv import csv_response
from app.modules.reporting.periods import GroupBy, PeriodPreset, resolve_preset
from app.modules.reporting.schemas import (
    DashboardFinancial,
    DashboardSales,
    ExpenseBreakdownPublic,
    MovementReportPublic,
    ProductPerformanceFinancial,
    ProductPerformancePublic,
    ProfitComparisonPublic,
    ProfitStatementPublic,
    ResolvedPeriod,
    SalesSummaryPublic,
    StockStatusPublic,
)
from app.modules.settings.service import get_settings

router = APIRouter(prefix="/reports", tags=["reports"])

SalesReader = Annotated[User, Depends(require_permission(Permission.REPORTS_SALES))]
InventoryReader = Annotated[
    User, Depends(require_permission(Permission.REPORTS_INVENTORY))
]
FinanceReader = Annotated[
    User, Depends(require_permission(Permission.REPORTS_FINANCIAL))
]
PaymentReader = Annotated[User, Depends(require_permission(Permission.PAYMENTS_READ))]
IncomeReader = Annotated[User, Depends(require_permission(Permission.FINANCE_VIEW))]


def _today(session: SessionDep) -> date:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo(get_settings(session).timezone))
    return now.date()


@router.get("/presets/{preset}", response_model=ResolvedPeriod)
def read_preset(
    session: SessionDep, _user: CurrentUser, preset: PeriodPreset
) -> ResolvedPeriod:
    start, end = resolve_preset(preset, _today(session))
    return ResolvedPeriod(preset=preset.value, date_from=start, date_to=end)


@router.get("/dashboard", response_model=DashboardSales | DashboardFinancial)
def read_dashboard(
    session: SessionDep,
    user: CurrentUser,
    date_from: date | None = None,
    date_to: date | None = None,
) -> DashboardSales | DashboardFinancial:
    today = _today(session)
    start = date_from or today
    end = date_to or today
    financial = has_permission(user, Permission.REPORTS_FINANCIAL)
    body = service.dashboard(session, date_from=start, date_to=end, financial=financial)
    model = DashboardFinancial if financial else DashboardSales
    return model.model_validate(body)


@router.get("/sales/summary", response_model=SalesSummaryPublic)
def read_sales_summary(
    session: SessionDep,
    _user: SalesReader,
    date_from: date = Query(),
    date_to: date = Query(),
    group_by: GroupBy = GroupBy.DAY,
    cashier_id: uuid.UUID | None = None,
    method_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    status: str | None = None,
) -> SalesSummaryPublic:
    return SalesSummaryPublic.model_validate(
        service.sales_summary(
            session,
            date_from=date_from,
            date_to=date_to,
            group_by=group_by,
            cashier_id=cashier_id,
            method_id=method_id,
            category_id=category_id,
            status=status,
        )
    )


@router.get("/sales/summary.csv")
def export_sales_summary(
    session: SessionDep,
    _user: SalesReader,
    date_from: date = Query(),
    date_to: date = Query(),
    group_by: GroupBy = GroupBy.DAY,
    cashier_id: uuid.UUID | None = None,
    method_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    status: str | None = None,
):
    report = service.sales_summary(
        session,
        date_from=date_from,
        date_to=date_to,
        group_by=group_by,
        cashier_id=cashier_id,
        method_id=method_id,
        category_id=category_id,
        status=status,
    )
    rows = [
        [
            row["period_start"],
            row["gross_sales"],
            row["discounts"],
            row["refunds"],
            row["net_sales"],
            row["order_count"],
            row["average_order_value"],
        ]
        for row in report["data"]  # type: ignore[index]
    ]
    return csv_response(
        "sales-summary",
        date_from,
        date_to,
        [
            "period_start",
            "gross_sales",
            "discounts",
            "refunds",
            "net_sales",
            "order_count",
            "average_order_value",
        ],
        rows,
    )


@router.get(
    "/sales/products",
    response_model=ProductPerformancePublic | ProductPerformanceFinancial,
)
def read_products(
    session: SessionDep,
    user: SalesReader,
    date_from: date = Query(),
    date_to: date = Query(),
    cashier_id: uuid.UUID | None = None,
    method_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    status: str | None = None,
    sort: str = "quantity",
) -> ProductPerformancePublic | ProductPerformanceFinancial:
    financial = has_permission(user, Permission.REPORTS_FINANCIAL)
    body = service.product_performance(
        session,
        date_from=date_from,
        date_to=date_to,
        cashier_id=cashier_id,
        method_id=method_id,
        category_id=category_id,
        status=status,
        sort=sort,
        financial=financial,
    )
    model = ProductPerformanceFinancial if financial else ProductPerformancePublic
    return model.model_validate(body)


@router.get("/sales/products.csv")
def export_products(
    session: SessionDep,
    user: SalesReader,
    date_from: date = Query(),
    date_to: date = Query(),
    cashier_id: uuid.UUID | None = None,
    method_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    status: str | None = None,
    sort: str = "quantity",
):
    financial = has_permission(user, Permission.REPORTS_FINANCIAL)
    report = service.product_performance(
        session,
        date_from=date_from,
        date_to=date_to,
        cashier_id=cashier_id,
        method_id=method_id,
        category_id=category_id,
        status=status,
        sort=sort,
        financial=financial,
    )
    header = ["name", "quantity", "gross_sales", "discounts", "net_sales", "share"]
    if financial:
        header += ["estimated_cost", "estimated_gross_profit"]
    rows = [[row.get(column) for column in header] for row in report["data"]]  # type: ignore[index]
    return csv_response("product-performance", date_from, date_to, header, rows)


@router.get("/inventory/movements", response_model=MovementReportPublic)
def read_movements(
    session: SessionDep,
    _user: InventoryReader,
    date_from: date = Query(),
    date_to: date = Query(),
    category_id: uuid.UUID | None = None,
    item_type: str | None = None,
    is_active: bool | None = None,
) -> MovementReportPublic:
    return MovementReportPublic.model_validate(
        service.movement_summary(
            session,
            date_from=date_from,
            date_to=date_to,
            category_id=category_id,
            item_type=item_type,
            is_active=is_active,
        )
    )


@router.get("/inventory/movements.csv")
def export_movements(
    session: SessionDep,
    _user: InventoryReader,
    date_from: date = Query(),
    date_to: date = Query(),
    category_id: uuid.UUID | None = None,
    item_type: str | None = None,
    is_active: bool | None = None,
):
    report = service.movement_summary(
        session,
        date_from=date_from,
        date_to=date_to,
        category_id=category_id,
        item_type=item_type,
        is_active=is_active,
    )
    header = [
        "sku",
        "name",
        "opening",
        "received",
        "consumed",
        "adjustments",
        "spoilage",
        "returns",
        "reversals",
        "closing",
        "closing_value",
    ]
    rows = [[row[column] for column in header] for row in report["data"]]  # type: ignore[index]
    return csv_response("inventory-movements", date_from, date_to, header, rows)


@router.get("/inventory/status", response_model=StockStatusPublic)
def read_stock_status(
    session: SessionDep,
    _user: InventoryReader,
    category_id: uuid.UUID | None = None,
    item_type: str | None = None,
    is_active: bool | None = None,
) -> StockStatusPublic:
    return StockStatusPublic.model_validate(
        service.stock_status(
            session, category_id=category_id, item_type=item_type, is_active=is_active
        )
    )


@router.get("/profit/expenses", response_model=ExpenseBreakdownPublic)
def read_expenses(
    session: SessionDep,
    _user: FinanceReader,
    date_from: date = Query(),
    date_to: date = Query(),
) -> ExpenseBreakdownPublic:
    return ExpenseBreakdownPublic.model_validate(
        service.expense_breakdown(session, date_from=date_from, date_to=date_to)
    )


@router.get("/profit/expenses.csv")
def export_expenses(
    session: SessionDep,
    _user: FinanceReader,
    date_from: date = Query(),
    date_to: date = Query(),
):
    report = service.expense_breakdown(session, date_from=date_from, date_to=date_to)
    rows = [
        [row["category_name"], row["amount"], row["share"]]
        for row in report["data"]  # type: ignore[index]
    ]
    return csv_response(
        "expense-breakdown",
        date_from,
        date_to,
        ["category", "amount", "share"],
        rows,
    )


@router.get("/profit/statement", response_model=ProfitStatementPublic)
def read_statement(
    session: SessionDep,
    _user: FinanceReader,
    date_from: date = Query(),
    date_to: date = Query(),
) -> ProfitStatementPublic:
    return ProfitStatementPublic.model_validate(
        service.profit_statement(session, date_from=date_from, date_to=date_to)
    )


@router.get("/profit/statement.csv")
def export_statement(
    session: SessionDep,
    _user: FinanceReader,
    date_from: date = Query(),
    date_to: date = Query(),
):
    report = service.profit_statement(session, date_from=date_from, date_to=date_to)
    header = [
        "net_sales",
        "cogs",
        "gross_profit",
        "gross_margin",
        "expenses",
        "operating_profit",
    ]
    return csv_response(
        "profit-statement",
        date_from,
        date_to,
        header,
        [[report[column] for column in header]],
    )


@router.get("/profit/comparison", response_model=ProfitComparisonPublic)
def read_comparison(
    session: SessionDep,
    _user: FinanceReader,
    date_from: date = Query(),
    date_to: date = Query(),
    compare_from: date | None = None,
    compare_to: date | None = None,
) -> ProfitComparisonPublic:
    return ProfitComparisonPublic.model_validate(
        service.profit_comparison(
            session,
            date_from=date_from,
            date_to=date_to,
            compare_from=compare_from,
            compare_to=compare_to,
        )
    )


@router.get("/payments.csv")
def export_payments(
    session: SessionDep,
    user: PaymentReader,
    date_from: date = Query(),
    date_to: date = Query(),
    method_id: uuid.UUID | None = None,
    status: PaymentStatus | None = None,
):
    listed = list_payments(
        session,
        actor=user,
        date_from=date_from,
        date_to=date_to,
        method_id=method_id,
        status=status,
        skip=0,
        limit=1_000_000,
    )
    rows = [
        [
            row.recorded_at,
            row.order_number,
            row.method_name,
            row.amount,
            row.status.value,
        ]
        for row in listed.data
    ]
    return csv_response(
        "payments",
        date_from,
        date_to,
        ["recorded_at", "order", "method", "amount", "status"],
        rows,
    )


@router.get("/income.csv")
def export_income(
    session: SessionDep,
    _user: IncomeReader,
    date_from: date = Query(),
    date_to: date = Query(),
):
    rows = income_listing(session, date_from=date_from, date_to=date_to)
    header = [
        "number",
        "completed_at",
        "gross_sales",
        "discounts",
        "refunds",
        "tax",
        "net_sales",
        "payment_status",
    ]
    return csv_response(
        "income",
        date_from,
        date_to,
        header,
        [[row[column] for column in header] for row in rows],
    )
