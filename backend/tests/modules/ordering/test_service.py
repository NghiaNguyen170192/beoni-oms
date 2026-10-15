import re
import uuid
from decimal import Decimal
from typing import Any

import pytest
from sqlmodel import Session

from app.models import User
from app.modules.catalog import service as catalog
from app.modules.catalog.errors import MenuItemInUse, MenuItemNotSellable
from app.modules.catalog.models import MenuItem
from app.modules.catalog.schemas import MenuItemUpdate
from app.modules.identity.roles import Role
from app.modules.ordering import service
from app.modules.ordering.errors import (
    EmptyOrder,
    InvalidOrderChange,
    OrderNotEditable,
    OrderNotFound,
    ReceiptUnavailable,
)
from app.modules.ordering.models import OrderType
from app.modules.ordering.pricing import DiscountType
from app.modules.ordering.schemas import (
    DiscountUpdate,
    OrderCancel,
    OrderCreate,
    OrderLineInput,
    OrderUpdate,
)
from app.modules.ordering.states import InvalidTransition, OrderStatus
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


def _line(item: MenuItem, qty: str = "1", **kw: Any) -> OrderLineInput:
    return OrderLineInput(menu_item_id=item.id, quantity=D(qty), **kw)


def _create(db: Session, actor: User, *lines: OrderLineInput, **kw: Any) -> Any:
    data = OrderCreate(
        order_type=kw.pop("order_type", OrderType.TAKEAWAY), lines=list(lines), **kw
    )
    return service.create_order(db, data=data, actor=actor)


def _complete(
    db: Session, actor: User, order_id: uuid.UUID, key: str | None = None
) -> Any:
    return service.complete_order(
        db, order_id=order_id, actor=actor, idempotency_key=key or uuid.uuid4().hex
    )


def test_new_takeaway_order_is_draft_with_number_and_cashier(
    db: Session, cashier: User
) -> None:
    order = _create(db, cashier)

    assert order.status == OrderStatus.DRAFT
    assert order.order_type == OrderType.TAKEAWAY
    assert order.cashier_id == cashier.id
    assert re.fullmatch(r"HD-\d{8}-\d{4,}", order.number)


def test_order_numbers_are_unique_and_sequential(db: Session, cashier: User) -> None:
    first = _create(db, cashier)
    second = _create(db, cashier)

    assert first.number != second.number
    assert (
        int(second.number.rsplit("-", 1)[1]) == int(first.number.rsplit("-", 1)[1]) + 1
    )


def test_add_item_snapshots_line(db: Session, cashier: User) -> None:
    item = make_menu_item(db, name="Cà phê sữa đá", price=D("29000"))

    order = _create(db, cashier, _line(item, "2"))

    [line] = order.lines
    assert (line.item_name, line.item_code, line.unit_price) == (
        item.name,
        item.code,
        D("29000.00"),
    )
    assert line.quantity == D("2") and line.line_total == D("58000")
    assert order.total == D("58000")


def test_zero_quantity_rejected() -> None:
    with pytest.raises(ValueError):
        OrderLineInput(menu_item_id=uuid.uuid4(), quantity=D("0"))
    with pytest.raises(ValueError):
        OrderLineInput(menu_item_id=uuid.uuid4(), quantity=D("1.0005"))


def test_unavailable_item_rejected(db: Session, cashier: User) -> None:
    item = make_menu_item(db, is_available=False)

    with pytest.raises(MenuItemNotSellable):
        _create(db, cashier, _line(item))


def test_replace_lines_add_change_remove(db: Session, cashier: User) -> None:
    coffee = make_menu_item(db, price=D("29000"))
    tea = make_menu_item(db, price=D("35000"))
    order = _create(db, cashier, _line(coffee))
    [coffee_line] = order.lines

    order = service.replace_lines(
        db,
        order_id=order.id,
        lines=[
            OrderLineInput(id=coffee_line.id, menu_item_id=coffee.id, quantity=D("3")),
            _line(tea, "1", note="ít đá"),
        ],
        actor=cashier,
    )
    assert [(line.item_code, line.quantity) for line in order.lines] == [
        (coffee.code, D("3")),
        (tea.code, D("1")),
    ]
    assert order.lines[0].id == coffee_line.id
    assert order.lines[1].note == "ít đá"
    assert order.total == D("122000")

    order = service.replace_lines(
        db, order_id=order.id, lines=[_line(tea, "2")], actor=cashier
    )
    assert [line.item_code for line in order.lines] == [tea.code]
    assert order.total == D("70000")


def test_unchanged_line_keeps_snapshot_changed_line_resnapshots(
    db: Session, cashier: User, manager: User
) -> None:
    item = make_menu_item(db, price=D("29000"))
    order = _create(db, cashier, _line(item))
    [line] = order.lines
    catalog.update_item(
        db, item_id=item.id, data=MenuItemUpdate(price=D("32000")), actor=manager
    )

    kept = service.replace_lines(
        db,
        order_id=order.id,
        lines=[OrderLineInput(id=line.id, menu_item_id=item.id, quantity=D("1"))],
        actor=cashier,
    )
    assert kept.lines[0].unit_price == D("29000")

    changed = service.replace_lines(
        db,
        order_id=order.id,
        lines=[OrderLineInput(id=line.id, menu_item_id=item.id, quantity=D("2"))],
        actor=cashier,
    )
    assert changed.lines[0].unit_price == D("32000")
    assert changed.total == D("64000")


def test_line_item_cannot_be_swapped(db: Session, cashier: User) -> None:
    coffee, tea = make_menu_item(db), make_menu_item(db)
    order = _create(db, cashier, _line(coffee))

    with pytest.raises(InvalidOrderChange):
        service.replace_lines(
            db,
            order_id=order.id,
            lines=[
                OrderLineInput(
                    id=order.lines[0].id, menu_item_id=tea.id, quantity=D("1")
                )
            ],
            actor=cashier,
        )


def test_completed_order_rejects_line_changes(db: Session, cashier: User) -> None:
    item = make_menu_item(db)
    order = _create(db, cashier, _line(item))
    _complete(db, cashier, order.id)

    with pytest.raises(OrderNotEditable):
        service.replace_lines(
            db, order_id=order.id, lines=[_line(item, "2")], actor=cashier
        )


def test_spec_totals_with_order_discount(
    db: Session, cashier: User, manager: User
) -> None:
    coffee = make_menu_item(db, price=D("29000"))
    tea = make_menu_item(db, price=D("35000"))
    order = _create(db, cashier, _line(coffee, "2"), _line(tea))

    order = service.set_order_discount(
        db,
        order_id=order.id,
        data=DiscountUpdate(discount_type=DiscountType.PERCENT, discount_value=D("10")),
        actor=manager,
    )

    assert (order.subtotal, order.discount_total, order.total) == (
        D("93000"),
        D("9300"),
        D("83700"),
    )
    assert order.order_discount_by_id == manager.id
    assert sum(line.net_total for line in order.lines) == D("83700")


def test_line_discount_exceeding_line_rejected(
    db: Session, cashier: User, manager: User
) -> None:
    item = make_menu_item(db, price=D("30000"))
    order = _create(db, cashier, _line(item))

    with pytest.raises(InvalidOrderChange):
        service.set_line_discount(
            db,
            order_id=order.id,
            line_id=order.lines[0].id,
            data=DiscountUpdate(
                discount_type=DiscountType.AMOUNT, discount_value=D("50000")
            ),
            actor=manager,
        )


def test_line_discount_records_who_applied_it(
    db: Session, cashier: User, manager: User
) -> None:
    item = make_menu_item(db, price=D("30000"))
    order = _create(db, cashier, _line(item))

    order = service.set_line_discount(
        db,
        order_id=order.id,
        line_id=order.lines[0].id,
        data=DiscountUpdate(
            discount_type=DiscountType.AMOUNT, discount_value=D("5000")
        ),
        actor=manager,
    )

    assert order.lines[0].discount_by_id == manager.id
    assert order.total == D("25000")


def test_tax_rate_from_settings_is_snapshotted(db: Session, cashier: User) -> None:
    row = settings_service.get_settings(db)
    row.tax_rate = D("8")
    db.add(row)
    db.commit()
    item = make_menu_item(db, price=D("54000"))

    order = _create(db, cashier, _line(item, "2"))

    assert order.tax_rate == D("8")
    assert order.total == D("108000") and order.tax_total == D("8000")


def test_confirm_then_complete_records_time_and_user(
    db: Session, cashier: User
) -> None:
    order = _create(db, cashier, _line(make_menu_item(db)))
    order = service.confirm_order(db, order_id=order.id, actor=cashier)
    assert order.status == OrderStatus.CONFIRMED and order.confirmed_at

    result = _complete(db, cashier, order.id)

    assert result.body["status"] == "completed"
    assert result.body["completed_by_id"] == str(cashier.id)
    assert result.body["completed_at"]


def test_double_completion_same_key_returns_original(
    db: Session, cashier: User
) -> None:
    order = _create(db, cashier, _line(make_menu_item(db)))

    first = _complete(db, cashier, order.id, key="complete-once")
    second = _complete(db, cashier, order.id, key="complete-once")

    assert first == second
    with pytest.raises(InvalidTransition):
        _complete(db, cashier, order.id, key="another-key")


def test_empty_order_cannot_be_completed(db: Session, cashier: User) -> None:
    order = _create(db, cashier)

    with pytest.raises(EmptyOrder):
        _complete(db, cashier, order.id)
    assert (
        service.get_order(db, order_id=order.id, actor=cashier).status
        == OrderStatus.DRAFT
    )


def test_cancel_draft_keeps_lines(db: Session, cashier: User) -> None:
    order = _create(db, cashier, _line(make_menu_item(db)))

    order = service.cancel_order(
        db, order_id=order.id, data=OrderCancel(reason="customer left"), actor=cashier
    )

    assert order.status == OrderStatus.CANCELLED
    assert order.cancel_reason == "customer left"
    assert len(order.lines) == 1


def test_cancelling_completed_order_conflicts(db: Session, cashier: User) -> None:
    order = _create(db, cashier, _line(make_menu_item(db)))
    _complete(db, cashier, order.id)

    with pytest.raises(InvalidTransition):
        service.cancel_order(
            db, order_id=order.id, data=OrderCancel(reason="x"), actor=cashier
        )
    assert (
        service.get_order(db, order_id=order.id, actor=cashier).status
        == OrderStatus.COMPLETED
    )


def test_price_change_after_completion_does_not_alter_order(
    db: Session, cashier: User, manager: User
) -> None:
    item = make_menu_item(db, price=D("29000"))
    original_name = item.name
    order = _create(db, cashier, _line(item))
    _complete(db, cashier, order.id)

    catalog.update_item(
        db,
        item_id=item.id,
        data=MenuItemUpdate(price=D("32000"), name="New name"),
        actor=manager,
    )

    after = service.get_order(db, order_id=order.id, actor=cashier)
    assert after.lines[0].unit_price == D("29000")
    assert after.lines[0].item_name == original_name
    assert after.total == D("29000")


def test_sold_item_cannot_be_deleted(db: Session, cashier: User, manager: User) -> None:
    item = make_menu_item(db)
    _create(db, cashier, _line(item))

    with pytest.raises(MenuItemInUse):
        catalog.delete_item(db, item_id=item.id, actor=manager)


def test_cashier_only_sees_own_orders(
    db: Session, cashier: User, manager: User
) -> None:
    other = make_user_with_role(db, Role.CASHIER)
    mine = _create(db, cashier)
    theirs = _create(db, other)

    orders, _ = service.list_orders(db, actor=cashier, limit=500)
    ids = {o.id for o in orders}
    assert mine.id in ids and theirs.id not in ids
    with pytest.raises(OrderNotFound):
        service.get_order(db, order_id=theirs.id, actor=cashier)

    all_orders, _ = service.list_orders(db, actor=manager, limit=500)
    assert {mine.id, theirs.id} <= {o.id for o in all_orders}


def test_receipt_only_for_confirmed_and_later(db: Session, cashier: User) -> None:
    order = _create(db, cashier, _line(make_menu_item(db)))
    with pytest.raises(ReceiptUnavailable):
        service.get_receipt(db, order_id=order.id, actor=cashier)

    _complete(db, cashier, order.id)
    receipt = service.get_receipt(db, order_id=order.id, actor=cashier)
    assert receipt.business_name
    assert receipt.order.number == order.number
    assert receipt.timezone == "Asia/Ho_Chi_Minh"


def test_table_label_only_for_dine_in(db: Session, cashier: User) -> None:
    with pytest.raises(ValueError):
        OrderCreate(order_type=OrderType.TAKEAWAY, table_label="B3")

    order = _create(db, cashier, order_type=OrderType.DINE_IN, table_label="B3")
    assert order.table_label == "B3"

    order = service.update_order(
        db,
        order_id=order.id,
        data=OrderUpdate(order_type=OrderType.COUNTER),
        actor=cashier,
    )
    assert order.table_label is None
