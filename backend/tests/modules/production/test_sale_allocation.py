"""POS sells finished-goods lots, never raw materials (beoni-batches 3.6/3.7)."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlmodel import Session, select

from app.models import User
from app.modules.catalog.models import ProductType
from app.modules.identity.roles import Role
from app.modules.inventory.models import InventoryMovement, MovementType, Unit
from app.modules.ordering import service as ordering
from app.modules.ordering.models import Order, OrderType
from app.modules.ordering.schemas import OrderCreate, OrderLineInput
from app.modules.ordering.states import OrderStatus
from app.modules.payments.models import PaymentMethod, PaymentMethodKind
from app.modules.payments.schemas import PaymentCreate
from app.modules.payments.service import record_payment
from app.modules.production.models import FinishedGoodLot
from app.modules.recipes import service as recipes
from app.modules.recipes.errors import InsufficientStock
from app.modules.recipes.schemas import (
    RecipeLineCreate,
    RecipeVersionCreate,
    StockReturnCreate,
    StockReturnLineCreate,
)
from app.modules.settings import service as settings_service
from tests.utils.catalog import make_menu_item
from tests.utils.inventory import (
    assert_reconciled,
    balance_of,
    make_inventory_item,
    seed_stock,
)
from tests.utils.production import make_finished_good, make_lot
from tests.utils.user import make_user_with_role

D = Decimal


@pytest.fixture()
def manager(db: Session) -> User:
    return make_user_with_role(db, Role.MANAGER)


@pytest.fixture()
def cashier(db: Session) -> User:
    return make_user_with_role(db, Role.CASHIER)


def _sell(
    db: Session,
    actor: User,
    menu_item_id: uuid.UUID,
    *,
    quantity: str = "1",
    key: str | None = None,
):
    order = ordering.create_order(
        db,
        data=OrderCreate(
            order_type=OrderType.TAKEAWAY,
            lines=[OrderLineInput(menu_item_id=menu_item_id, quantity=D(quantity))],
        ),
        actor=actor,
    )
    method = db.exec(
        select(PaymentMethod).where(PaymentMethod.kind == PaymentMethodKind.CASH)
    ).first()
    assert method is not None
    record_payment(
        db,
        order_id=order.id,
        data=PaymentCreate(method_id=method.id, amount=order.total),
        actor=actor,
        idempotency_key=uuid.uuid4().hex,
    )
    completed = ordering.complete_order(
        db,
        order_id=order.id,
        actor=actor,
        idempotency_key=key or uuid.uuid4().hex,
    )
    return completed, order


def _sale_movements(db: Session, order_id: uuid.UUID) -> list[InventoryMovement]:
    return list(
        db.exec(
            select(InventoryMovement).where(
                InventoryMovement.source_type == "order",
                InventoryMovement.source_id == order_id,
                InventoryMovement.movement_type == MovementType.SALE_CONSUMPTION,
            )
        ).all()
    )


def _lot(db: Session, lot_id: uuid.UUID) -> FinishedGoodLot:
    lot = db.get(FinishedGoodLot, lot_id, populate_existing=True)
    assert lot is not None
    return lot


def test_sale_deducts_the_lot_and_leaves_raw_materials_untouched(
    db: Session, manager: User, cashier: User
) -> None:
    flan = make_menu_item(db, name="Flan", product_type=ProductType.DIRECT_SALE)
    batch, ingredient, flan_stock, lot = make_lot(
        db, manager, menu_item=flan, good=D("5")
    )
    ingredient_before = balance_of(db, ingredient.id).quantity

    result, order = _sell(db, cashier, flan.id, quantity="2")

    [line] = result.body["lines"]
    assert line["cogs_amount"] is None
    assert line["cost_uncertain"] is True
    assert line["recipe_version_id"] is None
    [allocation] = line["finished_good_allocations"]
    assert allocation["finished_good_lot_id"] == str(lot.id)
    assert allocation["lot_number"] == lot.lot_number
    assert allocation["batch_id"] == str(batch.id)
    assert D(allocation["quantity"]) == D("2")

    assert balance_of(db, flan_stock.id).quantity == D("3")
    assert _lot(db, lot.id).quantity_on_hand == D("3")
    assert balance_of(db, ingredient.id).quantity == ingredient_before
    [movement] = _sale_movements(db, order.id)
    assert movement.item_id == flan_stock.id
    assert movement.quantity == D("-2")
    assert_reconciled(db, flan_stock.id)


def test_sale_allocates_across_lots_in_finished_order(
    db: Session, manager: User, cashier: User
) -> None:
    flan = make_menu_item(db, name="Flan", product_type=ProductType.DIRECT_SALE)
    flan_stock = make_finished_good(db)
    _, _, _, first_lot = make_lot(
        db,
        manager,
        menu_item=flan,
        finished_good=flan_stock,
        good=D("5"),
        finished_at=datetime(2026, 5, 10, 12, tzinfo=timezone.utc),
    )
    _, _, _, second_lot = make_lot(
        db,
        manager,
        menu_item=flan,
        finished_good=flan_stock,
        good=D("5"),
        finished_at=datetime(2026, 5, 12, 12, tzinfo=timezone.utc),
    )

    result, _ = _sell(db, cashier, flan.id, quantity="8")

    [line] = result.body["lines"]
    allocations = line["finished_good_allocations"]
    assert [D(row["quantity"]) for row in allocations] == [D("5"), D("3")]
    assert allocations[0]["finished_good_lot_id"] == str(first_lot.id)
    assert allocations[1]["finished_good_lot_id"] == str(second_lot.id)
    assert _lot(db, first_lot.id).quantity_on_hand == D("0")
    assert _lot(db, second_lot.id).quantity_on_hand == D("2")


def test_shortage_rejects_even_when_negative_stock_is_enabled(
    db: Session, manager: User, cashier: User
) -> None:
    settings_service.get_settings(db).allow_negative_stock = True
    db.commit()
    flan = make_menu_item(db, name="Flan", product_type=ProductType.DIRECT_SALE)
    _, _, flan_stock, lot = make_lot(db, manager, menu_item=flan, good=D("5"))

    with pytest.raises(InsufficientStock) as exc_info:
        _sell(db, cashier, flan.id, quantity="6")

    [shortage] = exc_info.value.shortages
    assert shortage.item == flan_stock.name
    assert shortage.required == D("6")
    assert shortage.available == D("5")
    assert shortage.unit == Unit.PIECE.value
    assert _lot(db, lot.id).quantity_on_hand == D("5")
    assert balance_of(db, flan_stock.id).quantity == D("5")


def test_retry_with_the_same_key_posts_one_lot_movement(
    db: Session, manager: User, cashier: User
) -> None:
    flan = make_menu_item(db, name="Flan", product_type=ProductType.DIRECT_SALE)
    _, _, flan_stock, lot = make_lot(db, manager, menu_item=flan, good=D("5"))
    order = ordering.create_order(
        db,
        data=OrderCreate(
            order_type=OrderType.TAKEAWAY,
            lines=[OrderLineInput(menu_item_id=flan.id, quantity=D("1"))],
        ),
        actor=cashier,
    )
    method = db.exec(
        select(PaymentMethod).where(PaymentMethod.kind == PaymentMethodKind.CASH)
    ).first()
    assert method is not None
    record_payment(
        db,
        order_id=order.id,
        data=PaymentCreate(method_id=method.id, amount=order.total),
        actor=cashier,
        idempotency_key=uuid.uuid4().hex,
    )

    first = ordering.complete_order(
        db, order_id=order.id, actor=cashier, idempotency_key="sell-once"
    )
    second = ordering.complete_order(
        db, order_id=order.id, actor=cashier, idempotency_key="sell-once"
    )

    assert second.body == first.body
    assert _lot(db, lot.id).quantity_on_hand == D("4")
    assert len(_sale_movements(db, order.id)) == 1
    assert balance_of(db, flan_stock.id).quantity == D("4")


def test_sale_rolls_back_when_audit_fails(
    db: Session, manager: User, cashier: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    flan = make_menu_item(db, name="Flan", product_type=ProductType.DIRECT_SALE)
    _, _, flan_stock, lot = make_lot(db, manager, menu_item=flan, good=D("5"))
    order = ordering.create_order(
        db,
        data=OrderCreate(
            order_type=OrderType.TAKEAWAY,
            lines=[OrderLineInput(menu_item_id=flan.id, quantity=D("2"))],
        ),
        actor=cashier,
    )
    method = db.exec(
        select(PaymentMethod).where(PaymentMethod.kind == PaymentMethodKind.CASH)
    ).first()
    assert method is not None
    record_payment(
        db,
        order_id=order.id,
        data=PaymentCreate(method_id=method.id, amount=order.total),
        actor=cashier,
        idempotency_key=uuid.uuid4().hex,
    )
    real = ordering.audit.record

    def boom(*args, **kwargs):
        if kwargs.get("action") == "completed":
            raise RuntimeError("audit failed")
        return real(*args, **kwargs)

    monkeypatch.setattr(ordering.audit, "record", boom)
    with pytest.raises(RuntimeError, match="audit failed"):
        ordering.complete_order(
            db, order_id=order.id, actor=cashier, idempotency_key=uuid.uuid4().hex
        )

    assert _sale_movements(db, order.id) == []
    assert _lot(db, lot.id).quantity_on_hand == D("5")
    assert balance_of(db, flan_stock.id).quantity == D("5")
    stored = db.get(Order, order.id)
    assert stored is not None and stored.status == OrderStatus.PAID


def _return(
    db: Session,
    actor: User,
    order_id: uuid.UUID,
    line_id: uuid.UUID,
    *,
    quantity: str = "1",
    sellable: bool = True,
):
    return recipes.return_to_stock(
        db,
        order_id=order_id,
        data=StockReturnCreate(
            reason="unopened",
            lines=[
                StockReturnLineCreate(
                    order_line_id=line_id,
                    quantity=D(quantity),
                    sellable=sellable,
                )
            ],
        ),
        actor=actor,
        idempotency_key=uuid.uuid4().hex,
    )


def test_sellable_return_restores_the_source_lot(
    db: Session, manager: User, cashier: User
) -> None:
    flan = make_menu_item(db, name="Flan", product_type=ProductType.DIRECT_SALE)
    _, _, flan_stock, lot = make_lot(db, manager, menu_item=flan, good=D("5"))
    _, order = _sell(db, cashier, flan.id, quantity="2")
    line_id = ordering._lines(db, order.id)[0].id

    returned = _return(db, manager, order.id, line_id)

    [return_line] = returned.body["lines"]
    assert return_line["sellable"] is True
    assert return_line["finished_good_lot_id"] == str(lot.id)
    assert return_line["lot_number"] == lot.lot_number
    assert return_line["movement_id"] is not None
    assert _lot(db, lot.id).quantity_on_hand == D("4")
    assert balance_of(db, flan_stock.id).quantity == D("4")
    assert_reconciled(db, flan_stock.id)


def test_non_sellable_return_does_not_restore_the_lot(
    db: Session, manager: User, cashier: User
) -> None:
    flan = make_menu_item(db, name="Flan", product_type=ProductType.DIRECT_SALE)
    _, _, flan_stock, lot = make_lot(db, manager, menu_item=flan, good=D("5"))
    _, order = _sell(db, cashier, flan.id, quantity="2")
    line_id = ordering._lines(db, order.id)[0].id

    returned = _return(db, manager, order.id, line_id, sellable=False)

    [return_line] = returned.body["lines"]
    assert return_line["movement_id"] is None
    assert _lot(db, lot.id).quantity_on_hand == D("3")
    assert balance_of(db, flan_stock.id).quantity == D("3")


def test_unmapped_product_does_not_move_inventory(
    db: Session, manager: User, cashier: User
) -> None:
    """A legacy ingredient recipe is a production template, not a POS deduction."""
    beans = make_inventory_item(
        db,
        name="Coffee beans",
        base_unit=Unit.G,
        purchase_unit=Unit.G,
        conversion_factor=D("1"),
    )
    seed_stock(db, beans, "1000", unit_cost="400", actor=manager)
    coffee = make_menu_item(db, name="Iced", product_type=ProductType.PREPARED)
    recipes.create_version(
        db,
        data=RecipeVersionCreate(
            menu_item_id=coffee.id,
            effective_from=datetime.now(timezone.utc),
            lines=[RecipeLineCreate(inventory_item_id=beans.id, quantity=D("18"))],
        ),
        actor=manager,
    )

    result, order = _sell(db, cashier, coffee.id)

    [line] = result.body["lines"]
    assert line["cogs_amount"] is None
    assert line["cost_uncertain"] is True
    assert line["finished_good_allocations"] == []
    assert _sale_movements(db, order.id) == []
    assert balance_of(db, beans.id).quantity == D("1000")
