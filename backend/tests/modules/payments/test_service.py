import uuid
from decimal import Decimal

import pytest
from sqlmodel import Session, func, select

from app.models import User
from app.modules.identity.roles import Role
from app.modules.inventory.models import InventoryMovement
from app.modules.ordering import service as ordering
from app.modules.ordering.models import Order, OrderType
from app.modules.ordering.schemas import OrderCreate, OrderLineInput
from app.modules.ordering.states import OrderStatus
from app.modules.payments import service
from app.modules.payments.errors import (
    Overpayment,
    OverRefund,
    PaymentMethodInactive,
    PaymentShort,
    RefundNotAllowed,
    VoidNotAllowed,
)
from app.modules.payments.models import PaymentMethod, PaymentMethodKind, PaymentStatus
from app.modules.payments.schemas import (
    PaymentCreate,
    PaymentMethodUpdate,
    PaymentVoid,
    RefundCreate,
    RefundLineIn,
)
from app.modules.settings import service as settings_service
from tests.utils.catalog import make_menu_item
from tests.utils.user import make_user_with_role

D = Decimal


@pytest.fixture(autouse=True)
def zero_tax(db: Session) -> None:
    row = settings_service.get_settings(db)
    row.tax_rate = D("0")
    db.add(row)
    db.commit()


@pytest.fixture()
def cashier(db: Session) -> User:
    return make_user_with_role(db, Role.CASHIER)


@pytest.fixture()
def manager(db: Session) -> User:
    return make_user_with_role(db, Role.MANAGER)


def _method(db: Session, kind: PaymentMethodKind) -> PaymentMethod:
    method = db.exec(
        select(PaymentMethod).where(
            PaymentMethod.kind == kind, PaymentMethod.is_active == True  # noqa: E712
        )
    ).first()
    assert method is not None
    return method


def _order(db: Session, actor: User, price: str, qty: str = "1") -> Order:
    item = make_menu_item(db, price=D(price))
    created = ordering.create_order(
        db,
        data=OrderCreate(
            order_type=OrderType.TAKEAWAY,
            lines=[OrderLineInput(menu_item_id=item.id, quantity=D(qty))],
        ),
        actor=actor,
    )
    order = db.get(Order, created.id)
    assert order is not None
    return order


def _pay(
    db: Session,
    actor: User,
    order: Order,
    *,
    method: PaymentMethod | None = None,
    amount: str | None = None,
    tendered: str | None = None,
    key: str | None = None,
):
    return service.record_payment(
        db,
        order_id=order.id,
        data=PaymentCreate(
            method_id=(method or _method(db, PaymentMethodKind.CASH)).id,
            amount=None if amount is None else D(amount),
            tendered=None if tendered is None else D(tendered),
        ),
        actor=actor,
        idempotency_key=key or uuid.uuid4().hex,
    )


def test_cash_tender_caps_at_remaining_and_returns_change(
    db: Session, cashier: User
) -> None:
    order = _order(db, cashier, "83700")
    result = _pay(db, cashier, order, tendered="100000")
    body = result.body

    assert result.status_code == 201
    assert body["amount"] == "83700.00"
    assert body["tendered"] == "100000.00"
    assert body["change_amount"] == "16300.00"
    db.refresh(order)
    assert order.status == OrderStatus.PAID


def test_bank_transfer_cannot_exceed_the_remaining_balance(
    db: Session, cashier: User
) -> None:
    order = _order(db, cashier, "83700")
    with pytest.raises(Overpayment):
        _pay(
            db,
            cashier,
            order,
            method=_method(db, PaymentMethodKind.BANK_TRANSFER),
            amount="90000",
        )


def test_partial_payment_stays_open_until_covered(db: Session, cashier: User) -> None:
    order = _order(db, cashier, "83700")
    _pay(db, cashier, order, amount="50000")
    db.refresh(order)
    assert order.status == OrderStatus.DRAFT

    _pay(db, cashier, order, amount="33700")
    db.refresh(order)
    assert order.status == OrderStatus.PAID


def test_void_drops_a_paid_order_back_to_confirmed(
    db: Session, cashier: User, manager: User
) -> None:
    order = _order(db, cashier, "29000")
    payment = _pay(db, cashier, order, amount="29000")
    voided = service.void_payment(
        db,
        payment_id=uuid.UUID(payment.body["id"]),
        data=PaymentVoid(reason="wrong tender"),
        actor=manager,
        idempotency_key=uuid.uuid4().hex,
    )

    assert voided.body["status"] == PaymentStatus.VOIDED.value
    db.refresh(order)
    assert order.status == OrderStatus.CONFIRMED
    assert service.active_paid(db, order.id) == D("0.00")


def test_completed_payment_cannot_be_voided(
    db: Session, cashier: User, manager: User
) -> None:
    order = _order(db, cashier, "29000")
    payment = _pay(db, cashier, order, amount="29000")
    ordering.complete_order(
        db, order_id=order.id, actor=cashier, idempotency_key=uuid.uuid4().hex
    )

    with pytest.raises(VoidNotAllowed):
        service.void_payment(
            db,
            payment_id=uuid.UUID(payment.body["id"]),
            data=PaymentVoid(reason="too late"),
            actor=manager,
            idempotency_key=uuid.uuid4().hex,
        )


def test_unpaid_completion_names_the_remaining_amount(
    db: Session, cashier: User
) -> None:
    order = _order(db, cashier, "29000")
    with pytest.raises(PaymentShort, match="29000.00"):
        ordering.complete_order(
            db, order_id=order.id, actor=cashier, idempotency_key=uuid.uuid4().hex
        )
    db.refresh(order)
    assert order.status == OrderStatus.DRAFT


def test_pay_and_complete_is_one_result_and_idempotent(
    db: Session, cashier: User
) -> None:
    order = _order(db, cashier, "29000")
    key = "pay-complete-1"
    data = PaymentCreate(
        method_id=_method(db, PaymentMethodKind.CASH).id, amount=D("29000")
    )
    first = service.pay_and_complete(
        db, order_id=order.id, data=data, actor=cashier, idempotency_key=key
    )
    second = service.pay_and_complete(
        db, order_id=order.id, data=data, actor=cashier, idempotency_key=key
    )

    assert first.status_code == 200
    assert first.body["status"] == "completed"
    assert second.body == first.body
    assert service.active_paid(db, order.id) == D("29000.00")


def test_inactive_method_rejected(db: Session, cashier: User, manager: User) -> None:
    method = _method(db, PaymentMethodKind.CASH)
    service.update_method(
        db,
        method_id=method.id,
        data=PaymentMethodUpdate(is_active=False),
        actor=manager,
    )
    order = _order(db, cashier, "29000")
    with pytest.raises(PaymentMethodInactive):
        _pay(db, cashier, order, method=method, amount="29000")


def test_partial_and_full_refund_do_not_move_stock(
    db: Session, cashier: User, manager: User
) -> None:
    order = _order(db, cashier, "29000", qty="2")
    _pay(db, cashier, order, amount="58000")
    ordering.complete_order(
        db, order_id=order.id, actor=cashier, idempotency_key=uuid.uuid4().hex
    )
    before = db.exec(select(func.count()).select_from(InventoryMovement)).one()
    line = ordering._lines(db, order.id)[0]
    cash = _method(db, PaymentMethodKind.CASH)

    partial = service.record_refund(
        db,
        order_id=order.id,
        data=RefundCreate(
            method_id=cash.id,
            amount=D("29000"),
            reason="one returned",
            lines=[RefundLineIn(order_line_id=line.id, quantity=D("1"), amount=D("29000"))],
        ),
        actor=manager,
        idempotency_key="refund-partial",
    )
    db.refresh(order)
    assert partial.status_code == 201
    assert order.status == OrderStatus.PARTIALLY_REFUNDED
    with pytest.raises(OverRefund):
        service.record_refund(
            db,
            order_id=order.id,
            data=RefundCreate(method_id=cash.id, amount=D("40000"), reason="too much"),
            actor=manager,
            idempotency_key="refund-over",
        )

    full = service.record_refund(
        db,
        order_id=order.id,
        data=RefundCreate(method_id=cash.id, amount=D("29000"), reason="the rest"),
        actor=manager,
        idempotency_key="refund-full",
    )
    db.refresh(order)
    assert full.body["amount"] == "29000.00"
    assert order.status == OrderStatus.REFUNDED
    after = db.exec(select(func.count()).select_from(InventoryMovement)).one()
    assert after == before


def test_refund_before_completion_rejected(db: Session, cashier: User, manager: User) -> None:
    order = _order(db, cashier, "29000")
    _pay(db, cashier, order, amount="29000")
    with pytest.raises(RefundNotAllowed):
        service.record_refund(
            db,
            order_id=order.id,
            data=RefundCreate(
                method_id=_method(db, PaymentMethodKind.CASH).id,
                amount=D("29000"),
                reason="too soon",
            ),
            actor=manager,
            idempotency_key=uuid.uuid4().hex,
        )
