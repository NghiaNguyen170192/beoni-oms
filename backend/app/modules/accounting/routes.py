import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.api.deps import SessionDep
from app.models import User
from app.modules.accounting import service
from app.modules.accounting.models import ExpensePaymentStatus
from app.modules.accounting.schemas import (
    CashAdjustmentCreate,
    CashAdjustmentPublic,
    CashMovementPublic,
    CashMovementsPublic,
    CategoryTotal,
    ExpenseCategoryCreate,
    ExpenseCategoryPublic,
    ExpenseCreate,
    ExpensePay,
    ExpensePublic,
    ExpensesPublic,
    FinancialSummaryPublic,
    IncomePublic,
    IncomeRow,
    MoneyAccountPublic,
    MoneyAccountsPublic,
    Reversal,
    StatementEntry,
    StatementPublic,
    SupplierPaymentCreate,
    SupplierPaymentPublic,
)
from app.modules.idempotency.dependencies import IdempotencyKeyDep
from app.modules.identity.dependencies import require_permission
from app.modules.identity.permissions import Permission

router = APIRouter(tags=["accounting"])
CashViewer = Annotated[User, Depends(require_permission(Permission.CASH_VIEW))]
CashAdjuster = Annotated[User, Depends(require_permission(Permission.CASH_ADJUST))]
ExpenseReader = Annotated[User, Depends(require_permission(Permission.EXPENSES_READ))]
ExpenseManager = Annotated[User, Depends(require_permission(Permission.EXPENSES_MANAGE))]
SupplierPayer = Annotated[User, Depends(require_permission(Permission.SUPPLIER_PAYMENTS_RECORD))]
SupplierReader = Annotated[User, Depends(require_permission(Permission.SUPPLIER_PAYMENTS_READ))]
FinanceViewer = Annotated[User, Depends(require_permission(Permission.FINANCE_VIEW))]


def _stored(result: Any) -> JSONResponse:
    return JSONResponse(result.body, status_code=result.status_code)


@router.get("/cash/accounts", response_model=MoneyAccountsPublic)
def read_accounts(session: SessionDep, _actor: CashViewer) -> Any:
    rows = [
        MoneyAccountPublic(
            id=account.id,
            name=account.name,
            kind=account.kind,
            balance=balance,
        )
        for account, balance in service.list_accounts(session)
    ]
    return MoneyAccountsPublic(data=rows, count=len(rows))


@router.get("/cash/movements", response_model=CashMovementsPublic)
def read_movements(
    session: SessionDep,
    _actor: CashViewer,
    account_id: uuid.UUID,
    date_from: date,
    date_to: date,
    source_type: str | None = None,
) -> Any:
    report = service.list_movements(
        session,
        account_id=account_id,
        date_from=date_from,
        date_to=date_to,
        source_type=source_type,
    )
    movements = [
        CashMovementPublic.model_validate(row) for row in report["movements"]  # type: ignore[union-attr]
    ]
    return CashMovementsPublic(
        opening=report["opening"],  # type: ignore[arg-type]
        inflows=report["inflows"],  # type: ignore[arg-type]
        outflows=report["outflows"],  # type: ignore[arg-type]
        closing=report["closing"],  # type: ignore[arg-type]
        data=movements,
        count=len(movements),
    )


@router.post("/cash/adjustments", response_model=CashAdjustmentPublic, status_code=201)
def create_adjustment(
    session: SessionDep,
    actor: CashAdjuster,
    idempotency_key: IdempotencyKeyDep,
    body: CashAdjustmentCreate,
) -> Any:
    result = service.record_adjustment(
        session,
        account_id=body.account_id,
        amount=body.amount,
        reason=body.reason,
        actor=actor,
        idempotency_key=idempotency_key,
    )
    return _stored(result)


@router.post(
    "/cash/adjustments/{adjustment_id}/reverse",
    response_model=CashAdjustmentPublic,
)
def reverse_adjustment(
    session: SessionDep,
    actor: CashAdjuster,
    idempotency_key: IdempotencyKeyDep,
    adjustment_id: uuid.UUID,
    body: Reversal,
) -> Any:
    result = service.reverse_adjustment(
        session,
        adjustment_id=adjustment_id,
        reason=body.reason,
        actor=actor,
        idempotency_key=idempotency_key,
    )
    return _stored(result)


@router.get("/expenses/categories", response_model=list[ExpenseCategoryPublic])
def read_categories(
    session: SessionDep, _actor: ExpenseReader, active_only: bool = False
) -> Any:
    return service.list_categories(session, active_only=active_only)


@router.post("/expenses/categories", response_model=ExpenseCategoryPublic, status_code=201)
def create_category(
    session: SessionDep, actor: ExpenseManager, body: ExpenseCategoryCreate
) -> Any:
    return service.create_category(session, name=body.name, actor=actor)


@router.post("/expenses/categories/{category_id}/deactivate", response_model=ExpenseCategoryPublic)
def deactivate_category(
    session: SessionDep, _actor: ExpenseManager, category_id: uuid.UUID
) -> Any:
    return service.deactivate_category(session, category_id=category_id)


@router.get("/expenses", response_model=ExpensesPublic)
def read_expenses(
    session: SessionDep,
    _actor: ExpenseReader,
    date_from: date | None = None,
    date_to: date | None = None,
    category_id: uuid.UUID | None = None,
    payment_status: ExpensePaymentStatus | None = None,
    include_reversed: bool = False,
) -> Any:
    rows, totals = service.list_expenses(
        session,
        date_from=date_from,
        date_to=date_to,
        category_id=category_id,
        payment_status=payment_status,
        include_reversed=include_reversed,
    )
    data = [ExpensePublic.model_validate(row) for row in rows]
    return ExpensesPublic(
        data=data,
        count=len(data),
        totals=[
            CategoryTotal(category_id=category, category_name=name, total=total)
            for category, name, total in totals
        ],
    )


@router.post("/expenses", response_model=ExpensePublic, status_code=201)
def create_expense(
    session: SessionDep,
    actor: ExpenseManager,
    idempotency_key: IdempotencyKeyDep,
    body: ExpenseCreate,
) -> Any:
    result = service.record_expense(
        session,
        category_id=body.category_id,
        amount=body.amount,
        expense_date=body.expense_date,
        description=body.description,
        payment_status=body.payment_status,
        account_id=body.account_id,
        actor=actor,
        idempotency_key=idempotency_key,
    )
    return _stored(result)


@router.post("/expenses/{expense_id}/pay", response_model=ExpensePublic)
def pay_expense(
    session: SessionDep,
    actor: ExpenseManager,
    idempotency_key: IdempotencyKeyDep,
    expense_id: uuid.UUID,
    body: ExpensePay,
) -> Any:
    result = service.pay_expense(
        session,
        expense_id=expense_id,
        account_id=body.account_id,
        payment_date=body.payment_date,
        actor=actor,
        idempotency_key=idempotency_key,
    )
    return _stored(result)


@router.post("/expenses/{expense_id}/reverse", response_model=ExpensePublic)
def reverse_expense(
    session: SessionDep,
    actor: ExpenseManager,
    idempotency_key: IdempotencyKeyDep,
    expense_id: uuid.UUID,
    body: Reversal,
) -> Any:
    result = service.reverse_expense(
        session,
        expense_id=expense_id,
        reason=body.reason,
        actor=actor,
        idempotency_key=idempotency_key,
    )
    return _stored(result)


@router.post("/supplier-payments", response_model=SupplierPaymentPublic, status_code=201)
def create_supplier_payment(
    session: SessionDep,
    actor: SupplierPayer,
    idempotency_key: IdempotencyKeyDep,
    body: SupplierPaymentCreate,
) -> Any:
    result = service.record_supplier_payment(
        session,
        supplier_id=body.supplier_id,
        amount=body.amount,
        payment_date=body.payment_date,
        account_id=body.account_id,
        allocations=[(line.payable_id, line.amount) for line in body.allocations] or None,
        reference=body.reference,
        actor=actor,
        idempotency_key=idempotency_key,
    )
    return _stored(result)


@router.post(
    "/supplier-payments/{payment_id}/reverse", response_model=SupplierPaymentPublic
)
def reverse_supplier_payment(
    session: SessionDep,
    actor: SupplierPayer,
    idempotency_key: IdempotencyKeyDep,
    payment_id: uuid.UUID,
    body: Reversal,
) -> Any:
    result = service.reverse_supplier_payment(
        session,
        payment_id=payment_id,
        reason=body.reason,
        actor=actor,
        idempotency_key=idempotency_key,
    )
    return _stored(result)


@router.get(
    "/supplier-payments/suppliers/{supplier_id}/statement",
    response_model=StatementPublic,
)
def read_statement(
    session: SessionDep, _actor: SupplierReader, supplier_id: uuid.UUID
) -> Any:
    rows = [StatementEntry.model_validate(row) for row in service.supplier_statement(session, supplier_id)]
    return StatementPublic(data=rows, count=len(rows))


@router.get("/finance/summary", response_model=FinancialSummaryPublic)
def read_summary(
    session: SessionDep,
    _actor: FinanceViewer,
    date_from: date = Query(),
    date_to: date = Query(),
) -> Any:
    return service.financial_summary(session, date_from=date_from, date_to=date_to)


@router.get("/finance/income", response_model=IncomePublic)
def read_income(
    session: SessionDep,
    _actor: FinanceViewer,
    date_from: date = Query(),
    date_to: date = Query(),
) -> Any:
    rows = [IncomeRow.model_validate(row) for row in service.income_listing(session, date_from=date_from, date_to=date_to)]
    return IncomePublic(data=rows, count=len(rows))
