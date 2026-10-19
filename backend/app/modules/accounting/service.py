import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.errors import Invalid
from app.core.money import money
from app.models import User, get_datetime_utc
from app.modules.accounting.errors import (
    AdjustmentAlreadyReversed,
    AdjustmentNotFound,
    AllocationMismatch,
    ExpenseAlreadyPaid,
    ExpenseAlreadyReversed,
    ExpenseCategoryNotFound,
    ExpenseNotFound,
    OverAllocation,
    PaidExpenseNeedsAccount,
    SupplierPaymentAlreadyReversed,
    SupplierPaymentNotFound,
)
from app.modules.accounting.ledger import record_money_movement
from app.modules.accounting.models import (
    CashAdjustment,
    CashMovement,
    Expense,
    ExpenseCategory,
    ExpensePaymentStatus,
    MoneyAccount,
    RecordStatus,
    SupplierPayment,
    SupplierPaymentAllocation,
)
from app.modules.accounting.periods import noon_on, period_bounds
from app.modules.audit import service as audit
from app.modules.idempotency import service as idempotency
from app.modules.idempotency.service import StoredResponse
from app.modules.inventory.models import InventoryMovement, MovementType
from app.modules.ordering.models import Order, OrderLine
from app.modules.ordering.states import OrderStatus
from app.modules.payments.models import Payment, PaymentStatus, Refund
from app.modules.production.models import ProductionBatch, ProductionBatchStatus
from app.modules.purchasing.models import (
    PayableStatus,
    ReceiptStatus,
    StockReceipt,
    SupplierPayable,
)
from app.modules.settings.service import get_settings

SALE_STATUSES = (
    OrderStatus.COMPLETED,
    OrderStatus.PARTIALLY_REFUNDED,
    OrderStatus.REFUNDED,
)


def _zone(session: Session) -> str:
    return get_settings(session).timezone


def _payable_status(payable: SupplierPayable) -> None:
    if payable.paid_amount <= 0:
        payable.paid_amount = Decimal("0.00")
        payable.status = PayableStatus.UNPAID
    elif payable.paid_amount >= payable.amount:
        payable.status = PayableStatus.PAID
    else:
        payable.status = PayableStatus.PARTIALLY_PAID


def list_accounts(session: Session) -> list[tuple[MoneyAccount, Decimal]]:
    rows = session.exec(select(MoneyAccount).order_by(col(MoneyAccount.name))).all()
    totals = dict(
        session.exec(
            select(
                CashMovement.account_id, func.coalesce(func.sum(CashMovement.amount), 0)
            ).group_by(CashMovement.account_id)
        ).all()
    )
    return [(account, money(totals.get(account.id, Decimal("0")))) for account in rows]


def list_movements(
    session: Session,
    *,
    account_id: uuid.UUID,
    date_from: date,
    date_to: date,
    source_type: str | None = None,
) -> dict[str, object]:
    start, end = period_bounds(date_from, date_to, _zone(session))
    opening = session.exec(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.account_id == account_id,
            CashMovement.occurred_at < start,
        )
    ).one()
    query = select(CashMovement).where(
        CashMovement.account_id == account_id,
        CashMovement.occurred_at >= start,
        CashMovement.occurred_at < end,
    )
    if source_type:
        query = query.where(CashMovement.source_type == source_type)
    rows = list(session.exec(query.order_by(col(CashMovement.occurred_at))).all())
    inflows = money(sum((row.amount for row in rows if row.amount > 0), Decimal("0")))
    outflows = money(sum((-row.amount for row in rows if row.amount < 0), Decimal("0")))
    opening_amount = money(opening)
    return {
        "opening": opening_amount,
        "inflows": inflows,
        "outflows": outflows,
        "closing": money(opening_amount + inflows - outflows),
        "movements": rows,
    }


def record_adjustment(
    session: Session,
    *,
    account_id: uuid.UUID,
    amount: Decimal,
    reason: str,
    actor: User,
    idempotency_key: str,
) -> StoredResponse:
    signed = money(amount)
    if signed == 0:
        raise Invalid("Adjustment amount cannot be zero")

    def operation() -> tuple[int, CashAdjustment]:
        adjustment = CashAdjustment(
            account_id=account_id,
            amount=signed,
            reason=reason.strip(),
            recorded_by_id=actor.id,
        )
        session.add(adjustment)
        session.flush()
        record_money_movement(
            session,
            account_id=account_id,
            amount=signed,
            occurred_at=adjustment.created_at,
            source_type="cash_adjustment",
            source_id=adjustment.id,
            actor_id=actor.id,
            note=adjustment.reason,
        )
        audit.record(
            session,
            actor=actor,
            entity_type="cash_adjustment",
            entity_id=adjustment.id,
            action="recorded",
            changes={"amount": signed, "reason": adjustment.reason},
        )
        return 201, adjustment

    return idempotency.execute(
        session,
        scope="cash.adjust",
        key=idempotency_key,
        payload={
            "account_id": str(account_id),
            "amount": str(signed),
            "reason": reason,
        },
        operation=operation,
    )


def reverse_adjustment(
    session: Session,
    *,
    adjustment_id: uuid.UUID,
    reason: str,
    actor: User,
    idempotency_key: str,
) -> StoredResponse:
    def operation() -> tuple[int, CashAdjustment]:
        original = session.get(CashAdjustment, adjustment_id)
        if original is None:
            raise AdjustmentNotFound()
        if (
            original.status != RecordStatus.RECORDED
            or original.reversal_of_id is not None
        ):
            raise AdjustmentAlreadyReversed()
        original.status = RecordStatus.REVERSED
        reversal = CashAdjustment(
            account_id=original.account_id,
            amount=money(-original.amount),
            reason=reason.strip(),
            reversal_of_id=original.id,
            recorded_by_id=actor.id,
        )
        session.add(reversal)
        session.flush()
        record_money_movement(
            session,
            account_id=original.account_id,
            amount=reversal.amount,
            occurred_at=reversal.created_at,
            source_type="cash_adjustment_reversal",
            source_id=reversal.id,
            actor_id=actor.id,
            note=reversal.reason,
        )
        return 201, reversal

    return idempotency.execute(
        session,
        scope="cash.adjust.reverse",
        key=idempotency_key,
        payload={"adjustment_id": str(adjustment_id), "reason": reason},
        operation=operation,
    )


def list_categories(
    session: Session, *, active_only: bool = False
) -> list[ExpenseCategory]:
    query = select(ExpenseCategory).order_by(col(ExpenseCategory.name))
    if active_only:
        query = query.where(ExpenseCategory.is_active == True)  # noqa: E712
    return list(session.exec(query).all())


def create_category(session: Session, *, name: str, actor: User) -> ExpenseCategory:
    category = ExpenseCategory(name=name.strip())
    session.add(category)
    session.flush()
    audit.record(
        session,
        actor=actor,
        entity_type="expense_category",
        entity_id=category.id,
        action="created",
        changes={"name": category.name},
    )
    session.commit()
    session.refresh(category)
    return category


def deactivate_category(session: Session, *, category_id: uuid.UUID) -> ExpenseCategory:
    category = session.get(ExpenseCategory, category_id)
    if category is None:
        raise ExpenseCategoryNotFound()
    category.is_active = False
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


def _category(session: Session, category_id: uuid.UUID) -> ExpenseCategory:
    category = session.get(ExpenseCategory, category_id)
    if category is None or not category.is_active:
        raise ExpenseCategoryNotFound()
    return category


def record_expense(
    session: Session,
    *,
    category_id: uuid.UUID,
    amount: Decimal,
    expense_date: date,
    description: str,
    payment_status: ExpensePaymentStatus,
    account_id: uuid.UUID | None,
    actor: User,
    idempotency_key: str,
) -> StoredResponse:
    value = money(amount)
    if value <= 0:
        raise Invalid("Expense amount must be greater than zero")
    if payment_status == ExpensePaymentStatus.PAID and account_id is None:
        raise PaidExpenseNeedsAccount()

    def operation() -> tuple[int, Expense]:
        _category(session, category_id)
        paid_at = (
            noon_on(expense_date, _zone(session))
            if payment_status == ExpensePaymentStatus.PAID
            else None
        )
        expense = Expense(
            category_id=category_id,
            amount=value,
            expense_date=expense_date,
            description=description.strip(),
            payment_status=payment_status,
            account_id=account_id,
            paid_at=paid_at,
            recorded_by_id=actor.id,
        )
        session.add(expense)
        session.flush()
        if paid_at is not None and account_id is not None:
            record_money_movement(
                session,
                account_id=account_id,
                amount=money(-value),
                occurred_at=paid_at,
                source_type="expense",
                source_id=expense.id,
                actor_id=actor.id,
                note=expense.description,
            )
        audit.record(
            session,
            actor=actor,
            entity_type="expense",
            entity_id=expense.id,
            action="recorded",
            changes={"amount": value, "payment_status": payment_status.value},
        )
        return 201, expense

    return idempotency.execute(
        session,
        scope="expense.record",
        key=idempotency_key,
        payload={
            "category_id": str(category_id),
            "amount": str(value),
            "expense_date": expense_date.isoformat(),
            "description": description,
            "payment_status": payment_status.value,
            "account_id": str(account_id) if account_id else None,
        },
        operation=operation,
    )


def pay_expense(
    session: Session,
    *,
    expense_id: uuid.UUID,
    account_id: uuid.UUID,
    payment_date: date,
    actor: User,
    idempotency_key: str,
) -> StoredResponse:
    def operation() -> tuple[int, Expense]:
        expense = session.get(Expense, expense_id)
        if expense is None:
            raise ExpenseNotFound()
        if expense.status != RecordStatus.RECORDED:
            raise ExpenseAlreadyReversed()
        if expense.payment_status == ExpensePaymentStatus.PAID:
            raise ExpenseAlreadyPaid()
        paid_at = noon_on(payment_date, _zone(session))
        expense.payment_status = ExpensePaymentStatus.PAID
        expense.account_id = account_id
        expense.paid_at = paid_at
        session.add(expense)
        session.flush()
        record_money_movement(
            session,
            account_id=account_id,
            amount=money(-expense.amount),
            occurred_at=paid_at,
            source_type="expense",
            source_id=expense.id,
            actor_id=actor.id,
            note=expense.description,
        )
        return 200, expense

    return idempotency.execute(
        session,
        scope="expense.pay",
        key=idempotency_key,
        payload={
            "expense_id": str(expense_id),
            "account_id": str(account_id),
            "payment_date": payment_date.isoformat(),
        },
        operation=operation,
    )


def reverse_expense(
    session: Session,
    *,
    expense_id: uuid.UUID,
    reason: str,
    actor: User,
    idempotency_key: str,
) -> StoredResponse:
    def operation() -> tuple[int, Expense]:
        expense = session.get(Expense, expense_id)
        if expense is None:
            raise ExpenseNotFound()
        if expense.status != RecordStatus.RECORDED:
            raise ExpenseAlreadyReversed()
        expense.status = RecordStatus.REVERSED
        expense.reversal_reason = reason.strip()
        session.add(expense)
        session.flush()
        if expense.payment_status == ExpensePaymentStatus.PAID and expense.account_id:
            record_money_movement(
                session,
                account_id=expense.account_id,
                amount=expense.amount,
                occurred_at=get_datetime_utc(),
                source_type="expense_reversal",
                source_id=expense.id,
                actor_id=actor.id,
                note=expense.reversal_reason,
            )
        return 200, expense

    return idempotency.execute(
        session,
        scope="expense.reverse",
        key=idempotency_key,
        payload={"expense_id": str(expense_id), "reason": reason},
        operation=operation,
    )


def list_expenses(
    session: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    category_id: uuid.UUID | None,
    payment_status: ExpensePaymentStatus | None,
    include_reversed: bool,
) -> tuple[list[Expense], list[tuple[uuid.UUID, str, Decimal]]]:
    query = select(Expense)
    if date_from is not None:
        query = query.where(Expense.expense_date >= date_from)
    if date_to is not None:
        query = query.where(Expense.expense_date <= date_to)
    if category_id is not None:
        query = query.where(Expense.category_id == category_id)
    if payment_status is not None:
        query = query.where(Expense.payment_status == payment_status)
    if not include_reversed:
        query = query.where(Expense.status == RecordStatus.RECORDED)
    rows = list(session.exec(query.order_by(col(Expense.expense_date).desc())).all())
    totals: dict[uuid.UUID, Decimal] = {}
    for row in rows:
        if row.status != RecordStatus.RECORDED:
            continue
        totals[row.category_id] = money(
            totals.get(row.category_id, Decimal("0")) + row.amount
        )
    names = {
        category.id: category.name
        for category in session.exec(select(ExpenseCategory)).all()
    }
    by_category = [
        (category_id, names.get(category_id, ""), total)
        for category_id, total in sorted(
            totals.items(), key=lambda item: names.get(item[0], "")
        )
    ]
    return rows, by_category


def _open_payables(
    session: Session, supplier_id: uuid.UUID, *, for_update: bool
) -> list[SupplierPayable]:
    query = (
        select(SupplierPayable)
        .join(StockReceipt, StockReceipt.id == SupplierPayable.receipt_id)
        .where(
            SupplierPayable.supplier_id == supplier_id,
            SupplierPayable.status.in_(  # type: ignore[attr-defined]
                [PayableStatus.UNPAID, PayableStatus.PARTIALLY_PAID]
            ),
        )
        .order_by(col(StockReceipt.posted_at), col(SupplierPayable.id))
    )
    if for_update:
        query = query.with_for_update()
    return list(session.exec(query).all())


def apply_supplier_payment(
    session: Session,
    *,
    supplier_id: uuid.UUID,
    amount: Decimal,
    payment_date: date,
    account_id: uuid.UUID,
    allocations: list[tuple[uuid.UUID, Decimal]] | None,
    reference: str | None,
    actor: User,
) -> SupplierPayment:
    """Stage a supplier payment and its outflow. The caller commits."""
    value = money(amount)
    if value <= 0:
        raise Invalid("Payment amount must be greater than zero")
    if allocations:
        payable_ids = sorted({payable_id for payable_id, _ in allocations})
        locked = list(
            session.exec(
                select(SupplierPayable)
                .where(col(SupplierPayable.id).in_(payable_ids))
                .order_by(col(SupplierPayable.id))
                .with_for_update()
            ).all()
        )
        by_id = {payable.id: payable for payable in locked}
        planned = [
            (by_id[payable_id], money(share)) for payable_id, share in allocations
        ]
    else:
        planned_rows = _open_payables(session, supplier_id, for_update=True)
        remaining = value
        planned = []
        for payable in planned_rows:
            outstanding = money(payable.amount - payable.paid_amount)
            share = outstanding if outstanding <= remaining else remaining
            if share > 0:
                planned.append((payable, share))
                remaining = money(remaining - share)
            if remaining == 0:
                break
        if remaining > 0:
            raise OverAllocation()
    if sum((share for _, share in planned), Decimal("0")) != value:
        raise AllocationMismatch()
    for payable, share in planned:
        if (
            payable.supplier_id != supplier_id
            or payable.status == PayableStatus.CANCELLED
        ):
            raise OverAllocation()
        outstanding = money(payable.amount - payable.paid_amount)
        if share <= 0 or share > outstanding:
            raise OverAllocation()
    payment = SupplierPayment(
        supplier_id=supplier_id,
        amount=value,
        payment_date=payment_date,
        account_id=account_id,
        reference=reference,
        recorded_by_id=actor.id,
    )
    session.add(payment)
    session.flush()
    for payable, share in planned:
        session.add(
            SupplierPaymentAllocation(
                payment_id=payment.id, payable_id=payable.id, amount=share
            )
        )
        payable.paid_amount = money(payable.paid_amount + share)
        _payable_status(payable)
        session.add(payable)
    record_money_movement(
        session,
        account_id=account_id,
        amount=money(-value),
        occurred_at=noon_on(payment_date, _zone(session)),
        source_type="supplier_payment",
        source_id=payment.id,
        actor_id=actor.id,
        note=reference,
    )
    session.flush()
    return payment


def record_supplier_payment(
    session: Session,
    *,
    supplier_id: uuid.UUID,
    amount: Decimal,
    payment_date: date,
    account_id: uuid.UUID,
    allocations: list[tuple[uuid.UUID, Decimal]] | None,
    reference: str | None,
    actor: User,
    idempotency_key: str,
) -> StoredResponse:
    def operation() -> tuple[int, SupplierPayment]:
        payment = apply_supplier_payment(
            session,
            supplier_id=supplier_id,
            amount=amount,
            payment_date=payment_date,
            account_id=account_id,
            allocations=allocations,
            reference=reference,
            actor=actor,
        )
        audit.record(
            session,
            actor=actor,
            entity_type="supplier_payment",
            entity_id=payment.id,
            action="recorded",
            changes={"amount": payment.amount, "supplier_id": supplier_id},
        )
        return 201, payment

    return idempotency.execute(
        session,
        scope="supplier_payment.record",
        key=idempotency_key,
        payload={
            "supplier_id": str(supplier_id),
            "amount": str(money(amount)),
            "payment_date": payment_date.isoformat(),
            "account_id": str(account_id),
            "allocations": [
                {"payable_id": str(payable_id), "amount": str(share)}
                for payable_id, share in (allocations or [])
            ],
        },
        operation=operation,
    )


def reverse_supplier_payment(
    session: Session,
    *,
    payment_id: uuid.UUID,
    reason: str,
    actor: User,
    idempotency_key: str,
) -> StoredResponse:
    def operation() -> tuple[int, SupplierPayment]:
        payment = session.get(SupplierPayment, payment_id)
        if payment is None:
            raise SupplierPaymentNotFound()
        if payment.status != RecordStatus.RECORDED:
            raise SupplierPaymentAlreadyReversed()
        shares = list(
            session.exec(
                select(SupplierPaymentAllocation)
                .where(SupplierPaymentAllocation.payment_id == payment.id)
                .order_by(col(SupplierPaymentAllocation.payable_id))
            ).all()
        )
        payable_ids = sorted(share.payable_id for share in shares)
        payables = {
            payable.id: payable
            for payable in session.exec(
                select(SupplierPayable)
                .where(col(SupplierPayable.id).in_(payable_ids))
                .order_by(col(SupplierPayable.id))
                .with_for_update()
            ).all()
        }
        for share in shares:
            payable = payables[share.payable_id]
            payable.paid_amount = money(payable.paid_amount - share.amount)
            _payable_status(payable)
            session.add(payable)
        payment.status = RecordStatus.REVERSED
        payment.reversal_reason = reason.strip()
        session.add(payment)
        session.flush()
        record_money_movement(
            session,
            account_id=payment.account_id,
            amount=payment.amount,
            occurred_at=get_datetime_utc(),
            source_type="supplier_payment_reversal",
            source_id=payment.id,
            actor_id=actor.id,
            note=payment.reversal_reason,
        )
        return 200, payment

    return idempotency.execute(
        session,
        scope="supplier_payment.reverse",
        key=idempotency_key,
        payload={"payment_id": str(payment_id), "reason": reason},
        operation=operation,
    )


def supplier_statement(
    session: Session, supplier_id: uuid.UUID
) -> list[dict[str, object]]:
    receipts = session.exec(
        select(StockReceipt)
        .where(
            StockReceipt.supplier_id == supplier_id,
            StockReceipt.status == ReceiptStatus.POSTED,
        )
        .order_by(col(StockReceipt.posted_at))
    ).all()
    payments = session.exec(
        select(SupplierPayment)
        .where(
            SupplierPayment.supplier_id == supplier_id,
            SupplierPayment.status == RecordStatus.RECORDED,
        )
        .order_by(col(SupplierPayment.payment_date), col(SupplierPayment.created_at))
    ).all()
    entries: list[tuple[datetime, dict[str, object]]] = []
    for receipt in receipts:
        when = receipt.posted_at or receipt.created_at
        entries.append(
            (
                when,
                {
                    "kind": "receipt",
                    "id": receipt.id,
                    "occurred_at": when,
                    "reference": receipt.reference,
                    "purchases": receipt.total_value,
                    "payments": Decimal("0.00"),
                },
            )
        )
    for payment in payments:
        when = noon_on(payment.payment_date, _zone(session))
        entries.append(
            (
                when,
                {
                    "kind": "payment",
                    "id": payment.id,
                    "occurred_at": when,
                    "reference": payment.reference,
                    "purchases": Decimal("0.00"),
                    "payments": payment.amount,
                },
            )
        )
    entries.sort(key=lambda item: item[0])
    running = Decimal("0.00")
    statement: list[dict[str, object]] = []
    for _, entry in entries:
        running = money(running + entry["purchases"] - entry["payments"])  # type: ignore[operator]
        entry["outstanding"] = running
        statement.append(entry)
    return statement


def financial_summary(
    session: Session, *, date_from: date, date_to: date
) -> dict[str, Decimal | int]:
    start, end = period_bounds(date_from, date_to, _zone(session))
    sales = session.exec(
        select(
            func.coalesce(func.sum(Order.subtotal), 0),
            func.coalesce(func.sum(Order.discount_total), 0),
            func.coalesce(func.sum(Order.tax_total), 0),
        ).where(
            col(Order.status).in_(SALE_STATUSES),
            Order.completed_at >= start,
            Order.completed_at < end,
        )
    ).one()
    refunds = session.exec(
        select(func.coalesce(func.sum(Refund.amount), 0)).where(
            Refund.recorded_at >= start,
            Refund.recorded_at < end,
        )
    ).one()
    sale_value = session.exec(
        select(func.coalesce(func.sum(InventoryMovement.value), 0)).where(
            InventoryMovement.movement_type == MovementType.SALE_CONSUMPTION,
            InventoryMovement.occurred_at >= start,
            InventoryMovement.occurred_at < end,
        )
    ).one()
    return_value = session.exec(
        select(func.coalesce(func.sum(InventoryMovement.value), 0)).where(
            InventoryMovement.movement_type == MovementType.RETURN,
            InventoryMovement.occurred_at >= start,
            InventoryMovement.occurred_at < end,
        )
    ).one()
    expenses = session.exec(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.status == RecordStatus.RECORDED,
            Expense.expense_date >= date_from,
            Expense.expense_date <= date_to,
        )
    ).one()
    production_cost = production_expense(session, date_from=date_from, date_to=date_to)
    uncertain = session.exec(
        select(func.count())
        .select_from(OrderLine)
        .join(Order, Order.id == OrderLine.order_id)
        .where(
            col(Order.status).in_(SALE_STATUSES),
            Order.completed_at >= start,
            Order.completed_at < end,
            OrderLine.cost_uncertain == True,  # noqa: E712
        )
    ).one()
    missing = session.exec(
        select(func.count())
        .select_from(OrderLine)
        .join(Order, Order.id == OrderLine.order_id)
        .where(
            col(Order.status).in_(SALE_STATUSES),
            Order.completed_at >= start,
            Order.completed_at < end,
            OrderLine.cogs_amount.is_(None),  # type: ignore[union-attr]
        )
    ).one()
    gross = money(sales[0])
    discounts = money(sales[1])
    tax = money(sales[2])
    refunded = money(refunds)
    cogs = money(-Decimal(sale_value) - Decimal(return_value))
    expense_total = money(Decimal(expenses or 0) + production_cost)
    net = money(gross - discounts - refunded)
    gross_profit = money(net - cogs)
    return {
        "gross_sales": gross,
        "discounts": discounts,
        "refunds": refunded,
        "tax": tax,
        "net_sales": net,
        "cogs": cogs,
        "gross_profit": gross_profit,
        "expenses": expense_total,
        "operating_profit": money(gross_profit - expense_total),
        "uncertain_cost_lines": int(uncertain or 0),
        "missing_cost_lines": int(missing or 0),
    }


def production_expense(session: Session, *, date_from: date, date_to: date) -> Decimal:
    start, end = period_bounds(date_from, date_to, _zone(session))
    completed_cost = session.exec(
        select(func.coalesce(func.sum(ProductionBatch.total_material_cost), 0)).where(
            ProductionBatch.status.in_(
                (ProductionBatchStatus.COMPLETED, ProductionBatchStatus.REVERSED)
            ),
            ProductionBatch.finished_at >= start,
            ProductionBatch.finished_at < end,
        )
    ).one()
    reversed_cost = session.exec(
        select(func.coalesce(func.sum(ProductionBatch.total_material_cost), 0)).where(
            ProductionBatch.status == ProductionBatchStatus.REVERSED,
            ProductionBatch.reversed_at >= start,
            ProductionBatch.reversed_at < end,
        )
    ).one()
    return money(Decimal(completed_cost or 0) - Decimal(reversed_cost or 0))


def income_listing(
    session: Session, *, date_from: date, date_to: date
) -> list[dict[str, object]]:
    start, end = period_bounds(date_from, date_to, _zone(session))
    orders = list(
        session.exec(
            select(Order)
            .where(
                col(Order.status).in_(SALE_STATUSES),
                Order.completed_at >= start,
                Order.completed_at < end,
            )
            .order_by(col(Order.completed_at))
        ).all()
    )
    if not orders:
        return []
    refund_rows = session.exec(
        select(Refund.order_id, func.coalesce(func.sum(Refund.amount), 0))
        .where(col(Refund.order_id).in_([order.id for order in orders]))
        .group_by(Refund.order_id)
    ).all()
    refunded = {order_id: money(total) for order_id, total in refund_rows}
    paid = dict(
        session.exec(
            select(Payment.order_id, func.coalesce(func.sum(Payment.amount), 0))
            .where(
                col(Payment.order_id).in_([order.id for order in orders]),
                Payment.status == PaymentStatus.ACTIVE,
            )
            .group_by(Payment.order_id)
        ).all()
    )
    rows: list[dict[str, object]] = []
    for order in orders:
        refund_amount = refunded.get(order.id, Decimal("0.00"))
        net = money(order.subtotal - order.discount_total - refund_amount)
        rows.append(
            {
                "order_id": order.id,
                "number": order.number,
                "completed_at": order.completed_at,
                "gross_sales": order.subtotal,
                "discounts": order.discount_total,
                "refunds": refund_amount,
                "tax": order.tax_total,
                "net_sales": net,
                "payment_status": order.status.value,
            }
        )
    return rows
