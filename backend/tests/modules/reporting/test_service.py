import uuid
from datetime import date
from decimal import Decimal

from sqlmodel import Session, select

from app.modules.accounting import service as accounting
from app.modules.accounting.ledger import BANK, account_named
from app.modules.accounting.models import ExpenseCategory, ExpensePaymentStatus
from app.modules.accounting.periods import noon_on
from app.modules.catalog.models import MenuItem
from app.modules.identity.roles import Role
from app.modules.inventory import service as inventory
from app.modules.inventory.models import InventoryBalance, ItemType, Unit
from app.modules.inventory.schemas import StockAdjustmentCreate
from app.modules.ordering import service as ordering
from app.modules.ordering.models import Order
from app.modules.ordering.schemas import OrderCancel, OrderCreate, OrderLineInput
from app.modules.ordering.states import OrderStatus
from app.modules.payments import service as payments
from app.modules.payments.models import (
    Payment,
    PaymentMethod,
    PaymentMethodKind,
    Refund,
)
from app.modules.payments.schemas import PaymentCreate, RefundCreate
from app.modules.reporting import service as reporting
from app.modules.reporting.periods import GroupBy
from app.modules.settings import service as settings_service
from tests.utils.catalog import make_menu_item
from tests.utils.inventory import balance_of, make_inventory_item, seed_stock
from tests.utils.user import make_user_with_role

D = Decimal
DAY = date(2024, 6, 15)


def _zero_tax(db: Session) -> None:
    row = settings_service.get_settings(db)
    row.tax_rate = D("0")
    db.add(row)
    db.commit()


def _complete_sale(db: Session, actor, item: MenuItem, qty: str = "1") -> Order:
    order = ordering.create_order(
        db,
        data=OrderCreate(
            order_type="takeaway",
            lines=[OrderLineInput(menu_item_id=item.id, quantity=D(qty))],
        ),
        actor=actor,
    )
    cash = db.exec(
        select(PaymentMethod).where(PaymentMethod.kind == PaymentMethodKind.CASH)
    ).first()
    assert cash is not None
    payments.record_payment(
        db,
        order_id=order.id,
        data=PaymentCreate(method_id=cash.id, tendered=item.price * D(qty)),
        actor=actor,
        idempotency_key=uuid.uuid4().hex,
    )
    ordering.complete_order(
        db, order_id=order.id, actor=actor, idempotency_key=uuid.uuid4().hex
    )
    stored = db.get(Order, order.id)
    assert stored is not None
    return stored


def test_dashboard_matches_financial_summary_and_empty_average(db: Session) -> None:
    _zero_tax(db)
    actor = make_user_with_role(db, Role.MANAGER)
    item = make_menu_item(db, price=D("100000"))
    _complete_sale(db, actor, item)
    today = date.today()
    board = reporting.dashboard(db, date_from=today, date_to=today, financial=True)
    summary = accounting.financial_summary(db, date_from=today, date_to=today)
    assert board["net_sales"] == summary["net_sales"]
    assert board["cogs"] == summary["cogs"]
    assert board["discounts"] == summary["discounts"]
    assert board["refunds"] == summary["refunds"]
    assert board["expenses"] == summary["expenses"]
    assert board["gross_profit"] == summary["gross_profit"]
    assert board["operating_profit"] == summary["operating_profit"]
    assert board["order_count"] >= 1
    empty = reporting.dashboard(
        db, date_from=date(2000, 1, 1), date_to=date(2000, 1, 1), financial=False
    )
    assert empty["order_count"] == 0
    assert empty["average_order_value"] == D("0.00")
    assert "cogs" not in empty


def test_product_totals_match_summary_and_skip_cancelled_and_renames(
    db: Session,
) -> None:
    _zero_tax(db)
    actor = make_user_with_role(db, Role.OWNER)
    tea = make_menu_item(db, name="Old tea", price=D("50000"))
    cake = make_menu_item(db, name="Cake", price=D("30000"))
    sold = _complete_sale(db, actor, tea, "2")
    _complete_sale(db, actor, cake, "1")
    cancelled = ordering.create_order(
        db,
        data=OrderCreate(
            order_type="takeaway",
            lines=[OrderLineInput(menu_item_id=tea.id, quantity=D("1"))],
        ),
        actor=actor,
    )
    ordering.cancel_order(
        db,
        order_id=cancelled.id,
        data=OrderCancel(reason="customer left"),
        actor=actor,
    )
    cash = db.exec(
        select(PaymentMethod).where(PaymentMethod.kind == PaymentMethodKind.CASH)
    ).one()
    payments.record_refund(
        db,
        order_id=sold.id,
        data=RefundCreate(method_id=cash.id, amount=D("10000"), reason="too sweet"),
        actor=actor,
        idempotency_key=uuid.uuid4().hex,
    )
    when = noon_on(DAY, "Asia/Ho_Chi_Minh")
    for order_id in (sold.id,):
        row = db.get(Order, order_id)
        assert row is not None
        row.completed_at = when
        db.add(row)
    cake_order = db.exec(
        select(Order)
        .where(Order.status == OrderStatus.COMPLETED)
        .order_by(Order.completed_at.desc())
    ).first()
    # Move every order this test completed onto the isolated day, including cake.
    for row in db.exec(select(Order).where(Order.cashier_id == actor.id)).all():
        if row.completed_at is not None and row.status != OrderStatus.CANCELLED:
            row.completed_at = when
            db.add(row)
    refund = db.exec(select(Refund).where(Refund.order_id == sold.id)).one()
    refund.recorded_at = when
    db.add(refund)
    tea.name = "New tea"
    db.add(tea)
    db.commit()

    summary = reporting.sales_summary(
        db, date_from=DAY, date_to=DAY, group_by=GroupBy.DAY, cashier_id=actor.id
    )
    products = reporting.product_performance(
        db,
        date_from=DAY,
        date_to=DAY,
        cashier_id=actor.id,
        financial=True,
        sort="quantity",
    )
    product_net = sum((row["net_sales"] for row in products["data"]), D("0"))
    product_qty = sum((row["quantity"] for row in products["data"]), D("0"))
    assert product_net == summary["net_sales"]
    assert summary["order_count"] == 2
    assert summary["refunds"] == D("10000.00")
    names = [row["name"] for row in products["data"]]
    assert names.count("New tea") == 1
    assert "Old tea" not in names
    assert products["data"][0]["best_seller"] is True
    assert product_qty == D("3")
    assert cake_order is not None


def test_payment_breakdown_nets_refunds(db: Session) -> None:
    _zero_tax(db)
    actor = make_user_with_role(db, Role.MANAGER)
    item = make_menu_item(db, price=D("1000000"))
    order = ordering.create_order(
        db,
        data=OrderCreate(
            order_type="takeaway",
            lines=[OrderLineInput(menu_item_id=item.id, quantity=D("1"))],
        ),
        actor=actor,
    )
    cash = db.exec(
        select(PaymentMethod).where(PaymentMethod.kind == PaymentMethodKind.CASH)
    ).one()
    bank = db.exec(
        select(PaymentMethod).where(
            PaymentMethod.kind == PaymentMethodKind.BANK_TRANSFER
        )
    ).one()
    payments.record_payment(
        db,
        order_id=order.id,
        data=PaymentCreate(method_id=cash.id, amount=D("600000")),
        actor=actor,
        idempotency_key=uuid.uuid4().hex,
    )
    payments.record_payment(
        db,
        order_id=order.id,
        data=PaymentCreate(method_id=bank.id, amount=D("400000")),
        actor=actor,
        idempotency_key=uuid.uuid4().hex,
    )
    ordering.complete_order(
        db, order_id=order.id, actor=actor, idempotency_key=uuid.uuid4().hex
    )
    payments.record_refund(
        db,
        order_id=order.id,
        data=RefundCreate(method_id=cash.id, amount=D("50000"), reason="change"),
        actor=actor,
        idempotency_key=uuid.uuid4().hex,
    )
    today = date.today()
    summary = reporting.sales_summary(
        db, date_from=today, date_to=today, group_by=GroupBy.DAY, cashier_id=actor.id
    )
    amounts = {row["method_name"]: row["amount"] for row in summary["payments"]}
    assert amounts[cash.name] == D("550000.00")
    assert amounts[bank.name] == D("400000.00")


def test_movement_identity_matches_balance(db: Session) -> None:
    actor = make_user_with_role(db, Role.INVENTORY_STAFF)
    item = make_inventory_item(
        db, base_unit=Unit.G, purchase_unit=Unit.G, conversion_factor=D("1")
    )
    seed_stock(db, item, "10", "1000", actor)
    inventory.post_adjustment(
        db,
        data=StockAdjustmentCreate.model_validate(
            {
                "lines": [
                    {
                        "item_id": str(item.id),
                        "reason": "spoilage",
                        "quantity_change": "-2",
                    }
                ]
            }
        ),
        actor=actor,
        idempotency_key=uuid.uuid4().hex,
    )
    today = date.today()
    report = reporting.movement_summary(db, date_from=today, date_to=today)
    row = next(entry for entry in report["data"] if entry["item_id"] == item.id)
    closing = (
        row["opening"]
        + row["received"]
        - row["consumed"]
        + row["adjustments"]
        + row["returns"]
        + row["reversals"]
    )
    assert closing == row["closing"]
    assert row["spoilage"] == D("-2.0000")
    assert row["consumed"] == D("0.0000")
    balance = balance_of(db, item.id)
    assert row["closing"] == balance.quantity
    packaging = make_inventory_item(
        db,
        item_type=ItemType.PACKAGING,
        base_unit=Unit.PIECE,
        purchase_unit=Unit.PIECE,
        conversion_factor=D("1"),
    )
    filtered = reporting.movement_summary(
        db, date_from=today, date_to=today, item_type="packaging"
    )
    ids = {entry["item_id"] for entry in filtered["data"]}
    assert packaging.id in ids
    assert item.id not in ids
    status = reporting.stock_status(db)
    assert status["total_value"] >= 0
    assert isinstance(status["negative_stock"], list)


def test_expense_share_and_profit_comparison(db: Session) -> None:
    actor = make_user_with_role(db, Role.ACCOUNTANT)
    bank = account_named(db, BANK)
    day = date(2024, 4, 2)
    previous = date(2024, 4, 1)
    for when, name, amount in (
        (day, "Rent", "10000000"),
        (day, "Utilities", "2000000"),
        (previous, "Rent", "8000000"),
    ):
        category = db.exec(
            select(ExpenseCategory).where(ExpenseCategory.name == name)
        ).one()
        accounting.record_expense(
            db,
            category_id=category.id,
            amount=D(amount),
            expense_date=when,
            description=name,
            payment_status=ExpensePaymentStatus.PAID,
            account_id=bank.id,
            actor=actor,
            idempotency_key=uuid.uuid4().hex,
        )
    breakdown = reporting.expense_breakdown(db, date_from=day, date_to=day)
    shares = {row["category_name"]: row["share"] for row in breakdown["data"]}
    assert shares["Rent"] == D("83.3")
    assert shares["Utilities"] == D("16.7")
    statement = reporting.profit_statement(db, date_from=day, date_to=day)
    assert statement["estimate"] is True
    assert statement["expenses"] == D("12000000.00")
    compared = reporting.profit_comparison(db, date_from=day, date_to=day)
    expense_line = next(row for row in compared["lines"] if row["key"] == "expenses")
    assert expense_line["current"] == D("12000000.00")
    assert expense_line["previous"] == D("8000000.00")
    assert expense_line["change"] == D("4000000.00")
    _ = InventoryBalance
    _ = Payment
