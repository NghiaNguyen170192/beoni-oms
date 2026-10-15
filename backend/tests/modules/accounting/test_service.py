import uuid
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlmodel import Session, col, func, select

from app.modules.accounting import service as accounting
from app.modules.accounting.errors import OverAllocation, PaidExpenseNeedsAccount
from app.modules.accounting.ledger import BANK, CASH_DRAWER, account_named
from app.modules.accounting.models import (
    CashMovement,
    Expense,
    ExpenseCategory,
    ExpensePaymentStatus,
    RecordStatus,
    SupplierPayment,
)
from app.modules.accounting.periods import period_bounds
from app.modules.identity.roles import Role
from app.modules.inventory.models import InventoryMovement, MovementType
from app.modules.ordering import service as ordering
from app.modules.ordering.models import Order, OrderLine
from app.modules.ordering.pricing import DiscountType
from app.modules.ordering.schemas import DiscountUpdate, OrderCreate, OrderLineInput
from app.modules.ordering.states import OrderStatus
from app.modules.payments import service as payments
from app.modules.payments.models import (
    Payment,
    PaymentMethod,
    PaymentMethodKind,
    PaymentStatus,
    Refund,
)
from app.modules.payments.schemas import PaymentCreate, PaymentVoid, RefundCreate
from app.modules.purchasing import service as purchasing
from app.modules.purchasing.errors import ReceiptHasPayments
from app.modules.purchasing.models import PayableStatus, SupplierPayable
from app.modules.purchasing.schemas import ReceiptCreate, ReceiptReverse, SupplierCreate
from app.modules.settings import service as settings_service
from tests.utils.catalog import make_menu_item
from tests.utils.inventory import make_inventory_item
from tests.utils.user import make_user_with_role

D = Decimal


@pytest.fixture(autouse=True)
def zero_tax(db: Session) -> None:
    row = settings_service.get_settings(db)
    row.tax_rate = D("0")
    db.add(row)
    db.commit()


def test_period_includes_late_night_in_ho_chi_minh() -> None:
    start, end = period_bounds(
        date(2026, 10, 14), date(2026, 10, 14), "Asia/Ho_Chi_Minh"
    )
    late = datetime(2026, 10, 14, 23, 30, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    assert start <= late.astimezone(ZoneInfo("UTC")) < end
    assert start == datetime(2026, 10, 13, 17, 0, tzinfo=ZoneInfo("UTC"))


def test_payment_refund_and_void_each_write_one_movement(db: Session) -> None:
    actor = make_user_with_role(db, Role.MANAGER)
    cash = db.exec(
        select(PaymentMethod).where(PaymentMethod.kind == PaymentMethodKind.CASH)
    ).first()
    assert cash is not None
    item = make_menu_item(db, price=D("29000"))
    order = ordering.create_order(
        db,
        data=OrderCreate(
            order_type="takeaway",
            lines=[OrderLineInput(menu_item_id=item.id, quantity=D("1"))],
        ),
        actor=actor,
    )
    payments.record_payment(
        db,
        order_id=order.id,
        data=PaymentCreate(method_id=cash.id, tendered=D("29000")),
        actor=actor,
        idempotency_key=uuid.uuid4().hex,
    )
    ordering.complete_order(
        db, order_id=order.id, actor=actor, idempotency_key=uuid.uuid4().hex
    )
    stored = db.exec(select(Payment).where(Payment.order_id == order.id)).one()
    inflow = db.exec(
        select(CashMovement).where(
            CashMovement.source_type == "payment", CashMovement.source_id == stored.id
        )
    ).one()
    assert inflow.amount == D("29000.00")
    assert inflow.account_id == account_named(db, CASH_DRAWER).id

    payments.record_refund(
        db,
        order_id=order.id,
        data=RefundCreate(method_id=cash.id, amount=D("29000"), reason="wrong"),
        actor=actor,
        idempotency_key=uuid.uuid4().hex,
    )
    refund = db.exec(select(Refund).where(Refund.order_id == order.id)).one()
    outflow = db.exec(
        select(CashMovement).where(
            CashMovement.source_type == "refund", CashMovement.source_id == refund.id
        )
    ).one()
    assert outflow.amount == D("-29000.00")

    draft = ordering.create_order(
        db,
        data=OrderCreate(
            order_type="takeaway",
            lines=[OrderLineInput(menu_item_id=item.id, quantity=D("1"))],
        ),
        actor=actor,
    )
    payments.record_payment(
        db,
        order_id=draft.id,
        data=PaymentCreate(method_id=cash.id, tendered=D("29000")),
        actor=actor,
        idempotency_key=uuid.uuid4().hex,
    )
    voidable = db.exec(
        select(Payment).where(
            Payment.order_id == draft.id, Payment.status == PaymentStatus.ACTIVE
        )
    ).one()
    payments.void_payment(
        db,
        payment_id=voidable.id,
        data=PaymentVoid(reason="mistake"),
        actor=actor,
        idempotency_key=uuid.uuid4().hex,
    )
    opposite = db.exec(
        select(CashMovement).where(
            CashMovement.source_type == "payment_void",
            CashMovement.source_id == voidable.id,
        )
    ).one()
    assert opposite.amount == D("-29000.00")


def test_backfill_matches_active_payments_minus_refunds(db: Session) -> None:
    movement_total = db.exec(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.source_type.in_(["payment", "payment_void", "refund"])  # type: ignore[attr-defined]
        )
    ).one()
    active = db.exec(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.status == PaymentStatus.ACTIVE
        )
    ).one()
    refunded = db.exec(select(func.coalesce(func.sum(Refund.amount), 0))).one()
    assert D(movement_total) == D(active) - D(refunded)


def test_cash_adjustment_increases_recorded_balance(db: Session) -> None:
    owner = make_user_with_role(db, Role.OWNER)
    account = account_named(db, CASH_DRAWER)
    before = next(
        amount for row, amount in accounting.list_accounts(db) if row.id == account.id
    )
    accounting.record_adjustment(
        db,
        account_id=account.id,
        amount=D("500000"),
        reason="opening float",
        actor=owner,
        idempotency_key="float-1",
    )
    accounting.record_adjustment(
        db,
        account_id=account.id,
        amount=D("500000"),
        reason="opening float",
        actor=owner,
        idempotency_key="float-1",
    )
    after = next(
        amount for row, amount in accounting.list_accounts(db) if row.id == account.id
    )
    assert after - before == D("500000.00")


def test_paid_expense_moves_bank_and_retry_is_idempotent(db: Session) -> None:
    accountant = make_user_with_role(db, Role.ACCOUNTANT)
    rent = db.exec(select(ExpenseCategory).where(ExpenseCategory.name == "Rent")).one()
    bank = account_named(db, BANK)
    with pytest.raises(PaidExpenseNeedsAccount):
        accounting.record_expense(
            db,
            category_id=rent.id,
            amount=D("10000000"),
            expense_date=date.today(),
            description="October rent",
            payment_status=ExpensePaymentStatus.PAID,
            account_id=None,
            actor=accountant,
            idempotency_key="rent-missing",
        )
    first = accounting.record_expense(
        db,
        category_id=rent.id,
        amount=D("10000000"),
        expense_date=date.today(),
        description="October rent",
        payment_status=ExpensePaymentStatus.PAID,
        account_id=bank.id,
        actor=accountant,
        idempotency_key="rent-1",
    )
    second = accounting.record_expense(
        db,
        category_id=rent.id,
        amount=D("10000000"),
        expense_date=date.today(),
        description="October rent",
        payment_status=ExpensePaymentStatus.PAID,
        account_id=bank.id,
        actor=accountant,
        idempotency_key="rent-1",
    )
    assert first.body["id"] == second.body["id"]
    movement = db.exec(
        select(CashMovement).where(
            CashMovement.source_id == uuid.UUID(first.body["id"])
        )
    ).one()
    assert movement.amount == D("-10000000.00")
    assert movement.account_id == bank.id


def test_unpaid_expense_can_be_paid_later_and_reversed(db: Session) -> None:
    accountant = make_user_with_role(db, Role.ACCOUNTANT)
    utilities = db.exec(
        select(ExpenseCategory).where(ExpenseCategory.name == "Utilities")
    ).one()
    cash = account_named(db, CASH_DRAWER)
    created = accounting.record_expense(
        db,
        category_id=utilities.id,
        amount=D("800000"),
        expense_date=date.today(),
        description="Electricity",
        payment_status=ExpensePaymentStatus.UNPAID,
        account_id=None,
        actor=accountant,
        idempotency_key="power-1",
    )
    expense_id = uuid.UUID(created.body["id"])
    accounting.pay_expense(
        db,
        expense_id=expense_id,
        account_id=cash.id,
        payment_date=date.today(),
        actor=accountant,
        idempotency_key="power-pay",
    )
    paid = db.exec(
        select(CashMovement).where(
            CashMovement.source_type == "expense", CashMovement.source_id == expense_id
        )
    ).one()
    assert paid.amount == D("-800000.00")
    accounting.reverse_expense(
        db,
        expense_id=expense_id,
        reason="wrong amount",
        actor=accountant,
        idempotency_key="power-reverse",
    )
    opposite = db.exec(
        select(CashMovement).where(CashMovement.source_type == "expense_reversal")
    ).one()
    assert opposite.amount == D("800000.00")


def _posted_receipt(db: Session, actor, cost: str) -> SupplierPayable:
    supplier = purchasing.create_supplier(
        db, data=SupplierCreate(name=f"Supplier {uuid.uuid4().hex[:6]}"), actor=actor
    )
    item = make_inventory_item(db)
    receipt = purchasing.create_receipt(
        db,
        data=ReceiptCreate.model_validate(
            {
                "supplier_id": str(supplier.id),
                "receipt_date": date.today().isoformat(),
                "lines": [
                    {
                        "item_id": str(item.id),
                        "purchase_quantity": "1",
                        "purchase_unit_cost": cost,
                    }
                ],
            }
        ),
        actor=actor,
    )
    purchasing.post_receipt(
        db, receipt_id=receipt.id, actor=actor, idempotency_key=uuid.uuid4().hex
    )
    payable = db.exec(
        select(SupplierPayable).where(SupplierPayable.receipt_id == receipt.id)
    ).one()
    return payable


def test_supplier_payment_allocates_and_blocks_receipt_reversal(db: Session) -> None:
    actor = make_user_with_role(db, Role.ACCOUNTANT)
    older = _posted_receipt(db, actor, "2000000")
    cash = account_named(db, CASH_DRAWER)
    accounting.record_supplier_payment(
        db,
        supplier_id=older.supplier_id,
        amount=D("1000000"),
        payment_date=date.today(),
        account_id=cash.id,
        allocations=[(older.id, D("1000000"))],
        reference=None,
        actor=actor,
        idempotency_key="pay-partial",
    )
    db.refresh(older)
    assert older.status == PayableStatus.PARTIALLY_PAID
    assert older.paid_amount == D("1000000.00")
    with pytest.raises(ReceiptHasPayments):
        purchasing.reverse_receipt(
            db,
            receipt_id=older.receipt_id,
            data=ReceiptReverse(reason="too late"),
            actor=actor,
            idempotency_key="reverse-paid",
        )
    with pytest.raises(OverAllocation):
        accounting.record_supplier_payment(
            db,
            supplier_id=older.supplier_id,
            amount=D("1500000"),
            payment_date=date.today(),
            account_id=cash.id,
            allocations=[(older.id, D("1500000"))],
            reference=None,
            actor=actor,
            idempotency_key="over",
        )


def test_supplier_payment_allocates_oldest_first(db: Session) -> None:
    actor = make_user_with_role(db, Role.ACCOUNTANT)
    supplier = purchasing.create_supplier(
        db, data=SupplierCreate(name=f"Mill {uuid.uuid4().hex[:6]}"), actor=actor
    )
    item = make_inventory_item(db)
    payables = []
    for cost in ("500000", "400000"):
        receipt = purchasing.create_receipt(
            db,
            data=ReceiptCreate.model_validate(
                {
                    "supplier_id": str(supplier.id),
                    "receipt_date": date.today().isoformat(),
                    "lines": [
                        {
                            "item_id": str(item.id),
                            "purchase_quantity": "1",
                            "purchase_unit_cost": cost,
                        }
                    ],
                }
            ),
            actor=actor,
        )
        purchasing.post_receipt(
            db, receipt_id=receipt.id, actor=actor, idempotency_key=uuid.uuid4().hex
        )
        payables.append(
            db.exec(
                select(SupplierPayable).where(SupplierPayable.receipt_id == receipt.id)
            ).one()
        )
    cash = account_named(db, CASH_DRAWER)
    accounting.record_supplier_payment(
        db,
        supplier_id=supplier.id,
        amount=D("700000"),
        payment_date=date.today(),
        account_id=cash.id,
        allocations=None,
        reference=None,
        actor=actor,
        idempotency_key="auto",
    )
    db.refresh(payables[0])
    db.refresh(payables[1])
    assert payables[0].paid_amount == D("500000.00")
    assert payables[1].paid_amount == D("200000.00")


def test_immediate_payment_on_receipt_and_reversal_restore_outstanding(
    db: Session,
) -> None:
    actor = make_user_with_role(db, Role.ACCOUNTANT)
    supplier = purchasing.create_supplier(
        db, data=SupplierCreate(name=f"Pay now {uuid.uuid4().hex[:6]}"), actor=actor
    )
    item = make_inventory_item(db)
    receipt = purchasing.create_receipt(
        db,
        data=ReceiptCreate.model_validate(
            {
                "supplier_id": str(supplier.id),
                "receipt_date": date.today().isoformat(),
                "lines": [
                    {
                        "item_id": str(item.id),
                        "purchase_quantity": "1",
                        "purchase_unit_cost": "2000000",
                    }
                ],
            }
        ),
        actor=actor,
    )
    cash = account_named(db, CASH_DRAWER)
    posted = purchasing.post_receipt(
        db,
        receipt_id=receipt.id,
        actor=actor,
        idempotency_key="deliver-1",
        payment_amount=D("2000000"),
        account_id=cash.id,
    )
    assert posted.status_code == 200
    payable = db.exec(
        select(SupplierPayable).where(SupplierPayable.receipt_id == receipt.id)
    ).one()
    assert payable.status == PayableStatus.PAID
    with pytest.raises(OverAllocation):
        accounting.record_supplier_payment(
            db,
            supplier_id=supplier.id,
            amount=D("1"),
            payment_date=date.today(),
            account_id=cash.id,
            allocations=None,
            reference=None,
            actor=actor,
            idempotency_key="should-fail-no-open",
        )
    stored = db.exec(
        select(CashMovement).where(CashMovement.source_type == "supplier_payment")
    ).all()
    assert any(row.amount == D("-2000000.00") for row in stored)
    payment = db.exec(
        select(SupplierPayment).where(SupplierPayment.supplier_id == supplier.id)
    ).one()
    accounting.reverse_supplier_payment(
        db,
        payment_id=payment.id,
        reason="paid the wrong supplier",
        actor=actor,
        idempotency_key="undo-deliver",
    )
    db.refresh(payable)
    assert payable.paid_amount == D("0.00")
    assert payable.status == PayableStatus.UNPAID


def test_financial_summary_formula(db: Session) -> None:
    actor = make_user_with_role(db, Role.MANAGER)
    category = db.exec(
        select(ExpenseCategory).where(ExpenseCategory.name == "Other")
    ).one()
    bank = account_named(db, BANK)
    accounting.record_expense(
        db,
        category_id=category.id,
        amount=D("200000"),
        expense_date=date.today(),
        description="Operating",
        payment_status=ExpensePaymentStatus.PAID,
        account_id=bank.id,
        actor=actor,
        idempotency_key="op-ex",
    )
    summary = accounting.financial_summary(
        db, date_from=date.today(), date_to=date.today()
    )
    assert (
        summary["net_sales"]
        == summary["gross_sales"] - summary["discounts"] - summary["refunds"]
    )
    assert summary["gross_profit"] == summary["net_sales"] - summary["cogs"]
    assert summary["operating_profit"] == summary["gross_profit"] - summary["expenses"]
    assert summary["expenses"] >= D("200000.00")


def test_seeded_documents_reconcile_with_summary_and_balances(db: Session) -> None:
    """Sales, a refund, a receipt payment, and an expense stay tied to source rows."""
    actor = make_user_with_role(db, Role.OWNER)
    cash_account = account_named(db, CASH_DRAWER)
    bank = account_named(db, BANK)
    before = {account.id: balance for account, balance in accounting.list_accounts(db)}
    method = db.exec(
        select(PaymentMethod).where(PaymentMethod.kind == PaymentMethodKind.CASH)
    ).first()
    assert method is not None

    item = make_menu_item(db, price=D("1000000"))
    order = ordering.create_order(
        db,
        data=OrderCreate(
            order_type="takeaway",
            lines=[OrderLineInput(menu_item_id=item.id, quantity=D("1"))],
        ),
        actor=actor,
    )
    ordering.set_order_discount(
        db,
        order_id=order.id,
        data=DiscountUpdate(
            discount_type=DiscountType.AMOUNT, discount_value=D("50000")
        ),
        actor=actor,
    )
    payments.record_payment(
        db,
        order_id=order.id,
        data=PaymentCreate(method_id=method.id, tendered=D("950000")),
        actor=actor,
        idempotency_key=uuid.uuid4().hex,
    )
    ordering.complete_order(
        db, order_id=order.id, actor=actor, idempotency_key=uuid.uuid4().hex
    )
    payments.record_refund(
        db,
        order_id=order.id,
        data=RefundCreate(method_id=method.id, amount=D("30000"), reason="Short pour"),
        actor=actor,
        idempotency_key=uuid.uuid4().hex,
    )

    supplier = purchasing.create_supplier(
        db, data=SupplierCreate(name=f"Reconcile {uuid.uuid4().hex[:6]}"), actor=actor
    )
    stock = make_inventory_item(db)
    receipt = purchasing.create_receipt(
        db,
        data=ReceiptCreate.model_validate(
            {
                "supplier_id": str(supplier.id),
                "receipt_date": date.today().isoformat(),
                "lines": [
                    {
                        "item_id": str(stock.id),
                        "purchase_quantity": "1",
                        "purchase_unit_cost": "1000000",
                    }
                ],
            }
        ),
        actor=actor,
    )
    purchasing.post_receipt(
        db, receipt_id=receipt.id, actor=actor, idempotency_key=uuid.uuid4().hex
    )
    accounting.record_supplier_payment(
        db,
        supplier_id=supplier.id,
        amount=D("400000"),
        payment_date=date.today(),
        account_id=cash_account.id,
        allocations=None,
        reference="REC-1",
        actor=actor,
        idempotency_key=uuid.uuid4().hex,
    )
    category = db.exec(
        select(ExpenseCategory).where(ExpenseCategory.name == "Rent")
    ).one()
    accounting.record_expense(
        db,
        category_id=category.id,
        amount=D("200000"),
        expense_date=date.today(),
        description="Shop rent",
        payment_status=ExpensePaymentStatus.PAID,
        account_id=bank.id,
        actor=actor,
        idempotency_key=uuid.uuid4().hex,
    )

    stored_order = db.get(Order, order.id)
    assert stored_order is not None
    assert stored_order.subtotal == D("1000000.00")
    assert stored_order.discount_total == D("50000.00")
    refunded = db.exec(
        select(func.coalesce(func.sum(Refund.amount), 0)).where(
            Refund.order_id == order.id
        )
    ).one()
    assert refunded == D("30000.00")
    payable = db.exec(
        select(SupplierPayable).where(SupplierPayable.receipt_id == receipt.id)
    ).one()
    assert payable.paid_amount == D("400000.00")
    assert payable.amount - payable.paid_amount == D("600000.00")

    after = {account.id: balance for account, balance in accounting.list_accounts(db)}
    assert after[cash_account.id] - before[cash_account.id] == D("520000.00")
    assert after[bank.id] - before[bank.id] == D("-200000.00")
    for account, balance in accounting.list_accounts(db):
        movement_total = db.exec(
            select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
                CashMovement.account_id == account.id
            )
        ).one()
        assert balance == movement_total

    today = date.today()
    start, end = period_bounds(today, today, "Asia/Ho_Chi_Minh")
    sales = db.exec(
        select(
            func.coalesce(func.sum(Order.subtotal), 0),
            func.coalesce(func.sum(Order.discount_total), 0),
            func.coalesce(func.sum(Order.tax_total), 0),
        ).where(
            col(Order.status).in_(
                [
                    OrderStatus.COMPLETED,
                    OrderStatus.PARTIALLY_REFUNDED,
                    OrderStatus.REFUNDED,
                ]
            ),
            Order.completed_at >= start,
            Order.completed_at < end,
        )
    ).one()
    period_refunds = db.exec(
        select(func.coalesce(func.sum(Refund.amount), 0)).where(
            Refund.recorded_at >= start,
            Refund.recorded_at < end,
        )
    ).one()
    sale_value = db.exec(
        select(func.coalesce(func.sum(InventoryMovement.value), 0)).where(
            InventoryMovement.movement_type == MovementType.SALE_CONSUMPTION,
            InventoryMovement.occurred_at >= start,
            InventoryMovement.occurred_at < end,
        )
    ).one()
    return_value = db.exec(
        select(func.coalesce(func.sum(InventoryMovement.value), 0)).where(
            InventoryMovement.movement_type == MovementType.RETURN,
            InventoryMovement.occurred_at >= start,
            InventoryMovement.occurred_at < end,
        )
    ).one()
    expense_total = db.exec(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.status == RecordStatus.RECORDED,
            Expense.expense_date >= today,
            Expense.expense_date <= today,
        )
    ).one()
    uncertain = db.exec(
        select(func.count())
        .select_from(OrderLine)
        .join(Order, Order.id == OrderLine.order_id)
        .where(
            col(Order.status).in_(
                [
                    OrderStatus.COMPLETED,
                    OrderStatus.PARTIALLY_REFUNDED,
                    OrderStatus.REFUNDED,
                ]
            ),
            Order.completed_at >= start,
            Order.completed_at < end,
            OrderLine.cost_uncertain == True,  # noqa: E712
        )
    ).one()
    missing = db.exec(
        select(func.count())
        .select_from(OrderLine)
        .join(Order, Order.id == OrderLine.order_id)
        .where(
            col(Order.status).in_(
                [
                    OrderStatus.COMPLETED,
                    OrderStatus.PARTIALLY_REFUNDED,
                    OrderStatus.REFUNDED,
                ]
            ),
            Order.completed_at >= start,
            Order.completed_at < end,
            OrderLine.cogs_amount.is_(None),  # type: ignore[union-attr]
        )
    ).one()
    summary = accounting.financial_summary(db, date_from=today, date_to=today)
    gross = D(sales[0]).quantize(D("0.01"))
    discounts = D(sales[1]).quantize(D("0.01"))
    refunds_total = D(period_refunds).quantize(D("0.01"))
    cogs = (-D(sale_value) - D(return_value)).quantize(D("0.01"))
    expenses = D(expense_total).quantize(D("0.01"))
    net = (gross - discounts - refunds_total).quantize(D("0.01"))
    assert summary["gross_sales"] == gross
    assert summary["discounts"] == discounts
    assert summary["refunds"] == refunds_total
    assert summary["cogs"] == cogs
    assert summary["expenses"] == expenses
    assert summary["net_sales"] == net
    assert summary["gross_profit"] == (net - cogs).quantize(D("0.01"))
    assert summary["operating_profit"] == (net - cogs - expenses).quantize(D("0.01"))
    assert summary["uncertain_cost_lines"] == int(uncertain or 0)
    assert summary["missing_cost_lines"] == int(missing or 0)
    assert gross >= D("1000000.00")
    assert discounts >= D("50000.00")
    assert refunds_total >= D("30000.00")
    assert expenses >= D("200000.00")

    book = accounting.list_movements(
        db, account_id=cash_account.id, date_from=today, date_to=today
    )
    assert book["closing"] == book["opening"] + book["inflows"] - book["outflows"]  # type: ignore[operator]
