import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlmodel import Session, col, func, select

from app.models import User
from app.modules.audit.models import AuditLog
from app.modules.catalog.models import ProductType
from app.modules.identity.roles import Role
from app.modules.inventory.errors import ItemInactive
from app.modules.inventory.models import (
    InventoryItem,
    InventoryMovement,
    MovementType,
    Unit,
)
from app.modules.ordering import service as ordering
from app.modules.ordering.models import Order, OrderLine
from app.modules.ordering.schemas import OrderCancel, OrderCreate, OrderLineInput
from app.modules.ordering.states import InvalidTransition, OrderStatus
from app.modules.payments.models import PaymentMethod, PaymentMethodKind
from app.modules.payments.schemas import PaymentCreate
from app.modules.payments.service import record_payment
from app.modules.recipes import service
from app.modules.recipes.errors import (
    InsufficientStock,
    MissingConsumption,
    PreparedReturnRejected,
    RecipeNotAllowed,
    ReturnExceedsSold,
)
from app.modules.recipes.models import MovementAllocation, RecipeKind
from app.modules.recipes.schemas import (
    RecipeLineCreate,
    RecipePublic,
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
from tests.utils.user import make_user_with_role

D = Decimal


@pytest.fixture(autouse=True)
def zero_tax(db: Session) -> None:
    row = settings_service.get_settings(db)
    row.tax_rate = D("0")
    row.allow_negative_stock = False
    db.add(row)
    db.commit()


@pytest.fixture()
def manager(db: Session) -> User:
    return make_user_with_role(db, Role.MANAGER)


@pytest.fixture()
def cashier(db: Session) -> User:
    return make_user_with_role(db, Role.CASHIER)


def _at(days: int = 0) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days)


def _ingredient(
    db: Session,
    name: str,
    unit: Unit,
    *,
    qty: str | None = "1000",
    cost: str = "1",
) -> InventoryItem:
    item = make_inventory_item(
        db,
        name=name,
        base_unit=unit,
        purchase_unit=unit,
        conversion_factor=D("1"),
    )
    if qty is not None:
        seed_stock(db, item, qty, cost)
    return item


def _version(
    db: Session,
    actor: User,
    menu_item_id: uuid.UUID,
    lines: list[tuple[uuid.UUID, str]],
    *,
    effective_from: datetime | None = None,
) -> RecipePublic:
    return service.create_version(
        db,
        data=RecipeVersionCreate(
            menu_item_id=menu_item_id,
            effective_from=effective_from or _at(-1),
            lines=[
                RecipeLineCreate(inventory_item_id=item_id, quantity=D(qty))
                for item_id, qty in lines
            ],
        ),
        actor=actor,
    )


def _pay(db: Session, actor: User, order_id: uuid.UUID) -> None:
    order = db.get(Order, order_id)
    assert order is not None
    method = db.exec(
        select(PaymentMethod).where(PaymentMethod.kind == PaymentMethodKind.CASH)
    ).first()
    assert method is not None
    if order.total > 0:
        record_payment(
            db,
            order_id=order_id,
            data=PaymentCreate(method_id=method.id, amount=order.total),
            actor=actor,
            idempotency_key=uuid.uuid4().hex,
        )


def _open(db: Session, actor: User, *lines: tuple[uuid.UUID, str]):
    created = ordering.create_order(
        db,
        data=OrderCreate(
            order_type=ordering.OrderType.TAKEAWAY,
            lines=[
                OrderLineInput(menu_item_id=item_id, quantity=D(qty))
                for item_id, qty in lines
            ],
        ),
        actor=actor,
    )
    return created


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


def test_iced_coffee_recipe_stores_base_unit_lines(db: Session, manager: User) -> None:
    beans = _ingredient(db, "Coffee beans", Unit.G, cost="400")
    milk = _ingredient(db, "Condensed milk", Unit.ML, cost="20")
    ice = _ingredient(db, "Ice", Unit.G, cost="1")
    cup = _ingredient(db, "Cup", Unit.CUP, cost="500")
    coffee = make_menu_item(db, name="Cà phê sữa đá", product_type=ProductType.PREPARED)

    recipe = _version(
        db,
        manager,
        coffee.id,
        [(beans.id, "18"), (milk.id, "30"), (ice.id, "150"), (cup.id, "1")],
    )

    assert recipe.kind == RecipeKind.RECIPE
    assert recipe.version == 1
    quantities = {line.item_name: line.quantity for line in recipe.lines}
    assert quantities == {
        "Coffee beans": D("18.0000"),
        "Condensed milk": D("30.0000"),
        "Ice": D("150.0000"),
        "Cup": D("1.0000"),
    }
    assert {line.base_unit for line in recipe.lines} == {
        Unit.G,
        Unit.ML,
        Unit.CUP,
    }


def test_recipe_on_non_stock_item_is_rejected(db: Session, manager: User) -> None:
    beans = _ingredient(db, "Beans", Unit.G)
    item = make_menu_item(db, product_type=ProductType.NON_STOCK)

    with pytest.raises(RecipeNotAllowed):
        _version(db, manager, item.id, [(beans.id, "18")])


def test_new_version_keeps_the_previous_lines(db: Session, manager: User) -> None:
    beans = _ingredient(db, "Coffee beans", Unit.G)
    coffee = make_menu_item(db, product_type=ProductType.PREPARED)
    first = _version(db, manager, coffee.id, [(beans.id, "18")])
    second = _version(db, manager, coffee.id, [(beans.id, "20")])

    versions, count = service.list_versions(db, menu_item_id=coffee.id)
    by_version = {row.version: row for row in versions}

    assert count == 2
    assert second.version == 2
    assert by_version[1].lines[0].quantity == D("18.0000")
    assert by_version[2].lines[0].quantity == D("20.0000")
    assert by_version[1].id == first.id


def test_future_version_is_not_applicable_today(db: Session, manager: User) -> None:
    beans = _ingredient(db, "Coffee beans", Unit.G)
    coffee = make_menu_item(db, product_type=ProductType.PREPARED)
    _version(db, manager, coffee.id, [(beans.id, "18")], effective_from=_at(-2))
    current = _version(
        db, manager, coffee.id, [(beans.id, "20")], effective_from=_at(-1)
    )
    _version(db, manager, coffee.id, [(beans.id, "22")], effective_from=_at(1))

    applicable = service.applicable_version(
        db, menu_item_id=coffee.id, kind=RecipeKind.RECIPE, at=_at(0)
    )

    assert applicable is not None
    assert applicable.id == current.id
    assert applicable.version == 2


def test_direct_sale_stock_link_is_one_item(db: Session, manager: User) -> None:
    bottle = _ingredient(db, "Aquafina 500ml", Unit.BOTTLE, qty="10", cost="5000")
    water = make_menu_item(db, name="Nước suối", product_type=ProductType.DIRECT_SALE)

    link = _version(db, manager, water.id, [(bottle.id, "1")])

    assert link.kind == RecipeKind.STOCK_LINK
    assert len(link.lines) == 1
    assert link.lines[0].quantity == D("1.0000")
    assert link.lines[0].item_name == "Aquafina 500ml"
    other = _ingredient(db, "Cup", Unit.CUP)
    with pytest.raises(RecipeNotAllowed):
        _version(db, manager, water.id, [(bottle.id, "1"), (other.id, "1")])


def test_version_creation_audits_old_and_new_lines(db: Session, manager: User) -> None:
    beans = _ingredient(db, "Coffee beans", Unit.G)
    coffee = make_menu_item(db, product_type=ProductType.PREPARED)
    first = _version(db, manager, coffee.id, [(beans.id, "18")])
    second = _version(db, manager, coffee.id, [(beans.id, "20")])

    entries = list(
        db.exec(
            select(AuditLog)
            .where(AuditLog.entity_type == "recipe")
            .where(col(AuditLog.entity_id).in_([str(first.id), str(second.id)]))
        ).all()
    )
    entries.sort(key=lambda entry: entry.changes["version"])

    assert len(entries) == 2
    assert entries[0].changes["lines"]["old"] == []
    assert D(entries[0].changes["lines"]["new"][0]["quantity"]) == D("18.0000")
    assert D(entries[1].changes["lines"]["old"][0]["quantity"]) == D("18.0000")
    assert D(entries[1].changes["lines"]["new"][0]["quantity"]) == D("20.0000")


def test_cost_preview_uses_current_average_and_flags_unknown(
    db: Session, manager: User
) -> None:
    beans = _ingredient(db, "Coffee beans", Unit.G, qty="1000", cost="400")
    other = _ingredient(db, "Other", Unit.PIECE, qty="10", cost="3000")
    unknown = _ingredient(db, "Unknown", Unit.G, qty=None)
    coffee = make_menu_item(db, product_type=ProductType.PREPARED)
    recipe = _version(
        db,
        manager,
        coffee.id,
        [(beans.id, "18"), (other.id, "1"), (unknown.id, "5")],
    )

    preview = service.cost_preview(db, recipe.id)

    by_name = {line.item_name: line for line in preview.lines}
    assert by_name["Coffee beans"].line_cost == D("7200.00")
    assert by_name["Coffee beans"].cost_unknown is False
    assert by_name["Unknown"].cost_unknown is True
    assert by_name["Unknown"].line_cost is None
    assert preview.estimated_cost == D("10200.00")


def test_inactive_inventory_item_rejected(db: Session, manager: User) -> None:
    beans = _ingredient(db, "Coffee beans", Unit.G)
    beans.is_active = False
    db.add(beans)
    db.commit()
    coffee = make_menu_item(db, product_type=ProductType.PREPARED)

    with pytest.raises(ItemInactive):
        _version(db, manager, coffee.id, [(beans.id, "18")])


def test_duplicate_line_in_the_payload_is_rejected() -> None:
    item_id = uuid.uuid4()
    with pytest.raises(ValueError):
        RecipeVersionCreate(
            menu_item_id=uuid.uuid4(),
            effective_from=_at(-1),
            lines=[
                RecipeLineCreate(inventory_item_id=item_id, quantity=D("1")),
                RecipeLineCreate(inventory_item_id=item_id, quantity=D("2")),
            ],
        )


def test_two_drinks_deduct_one_aggregated_movement(
    db: Session, manager: User, cashier: User
) -> None:
    beans = _ingredient(db, "Coffee beans", Unit.G, qty="1000", cost="400")
    iced = make_menu_item(db, name="Iced", product_type=ProductType.PREPARED)
    hot = make_menu_item(db, name="Hot", product_type=ProductType.PREPARED)
    _version(db, manager, iced.id, [(beans.id, "18")])
    _version(db, manager, hot.id, [(beans.id, "20")])
    order = _open(db, cashier, (iced.id, "2"), (hot.id, "1"))
    _pay(db, cashier, order.id)

    ordering.complete_order(
        db, order_id=order.id, actor=cashier, idempotency_key=uuid.uuid4().hex
    )

    [movement] = _sale_movements(db, order.id)
    assert movement.quantity == D("-56.0000")
    assert balance_of(db, beans.id).quantity == D("944.0000")
    assert_reconciled(db, beans.id)


def test_missing_recipe_names_the_item(db: Session, cashier: User) -> None:
    item = make_menu_item(db, name="Cà phê sữa đá", product_type=ProductType.PREPARED)
    order = _open(db, cashier, (item.id, "1"))
    _pay(db, cashier, order.id)

    with pytest.raises(MissingConsumption, match="Cà phê sữa đá"):
        ordering.complete_order(
            db, order_id=order.id, actor=cashier, idempotency_key=uuid.uuid4().hex
        )
    stored = db.get(Order, order.id)
    assert stored is not None and stored.status == OrderStatus.PAID
    assert _sale_movements(db, order.id) == []


def test_shortage_lists_required_and_available(
    db: Session, manager: User, cashier: User
) -> None:
    milk = _ingredient(db, "Milk", Unit.ML, qty="200", cost="10")
    drink = make_menu_item(db, product_type=ProductType.PREPARED)
    _version(db, manager, drink.id, [(milk.id, "300")])
    order = _open(db, cashier, (drink.id, "1"))
    _pay(db, cashier, order.id)

    with pytest.raises(InsufficientStock) as exc_info:
        ordering.complete_order(
            db, order_id=order.id, actor=cashier, idempotency_key=uuid.uuid4().hex
        )

    [shortage] = exc_info.value.shortages
    assert shortage.item == "Milk"
    assert shortage.required == D("300.0000")
    assert shortage.available == D("200.0000")
    assert shortage.unit == "ml"
    stored = db.get(Order, order.id)
    assert stored is not None and stored.status == OrderStatus.PAID
    assert balance_of(db, milk.id).quantity == D("200.0000")


def test_negative_stock_completes_and_flags_uncertain_cost(
    db: Session, manager: User, cashier: User
) -> None:
    settings_service.get_settings(db).allow_negative_stock = True
    db.commit()
    milk = _ingredient(db, "Milk", Unit.ML, qty="200", cost="10")
    drink = make_menu_item(db, product_type=ProductType.PREPARED)
    _version(db, manager, drink.id, [(milk.id, "300")])
    order = _open(db, cashier, (drink.id, "1"))
    _pay(db, cashier, order.id)

    ordering.complete_order(
        db, order_id=order.id, actor=cashier, idempotency_key=uuid.uuid4().hex
    )

    assert balance_of(db, milk.id).quantity == D("-100.0000")
    [movement] = _sale_movements(db, order.id)
    assert movement.cost_uncertain is True
    [line] = ordering._lines(db, order.id)
    assert line.cost_uncertain is True


def test_line_cogs_matches_recipe_cost_and_version(
    db: Session, manager: User, cashier: User
) -> None:
    beans = _ingredient(db, "Coffee beans", Unit.G, qty="1000", cost="400")
    other = _ingredient(db, "Other", Unit.PIECE, qty="10", cost="3000")
    coffee = make_menu_item(db, product_type=ProductType.PREPARED)
    recipe = _version(db, manager, coffee.id, [(beans.id, "18"), (other.id, "1")])
    order = _open(db, cashier, (coffee.id, "1"))
    _pay(db, cashier, order.id)

    result = ordering.complete_order(
        db, order_id=order.id, actor=cashier, idempotency_key=uuid.uuid4().hex
    )

    [line] = result.body["lines"]
    assert D(line["cogs_amount"]) == D("10200.00")
    assert line["recipe_version_id"] == str(recipe.id)


def test_later_recipe_change_does_not_rewrite_the_sale(
    db: Session, manager: User, cashier: User
) -> None:
    beans = _ingredient(db, "Coffee beans", Unit.G, qty="1000", cost="400")
    coffee = make_menu_item(db, product_type=ProductType.PREPARED)
    _version(db, manager, coffee.id, [(beans.id, "18")])
    order = _open(db, cashier, (coffee.id, "1"))
    _pay(db, cashier, order.id)
    ordering.complete_order(
        db, order_id=order.id, actor=cashier, idempotency_key=uuid.uuid4().hex
    )
    before_qty = balance_of(db, beans.id).quantity
    before_cogs = ordering._lines(db, order.id)[0].cogs_amount
    before_movements = len(_sale_movements(db, order.id))

    _version(db, manager, coffee.id, [(beans.id, "20")])

    assert balance_of(db, beans.id).quantity == before_qty
    assert ordering._lines(db, order.id)[0].cogs_amount == before_cogs
    assert len(_sale_movements(db, order.id)) == before_movements


def test_cancelling_a_draft_does_not_move_stock(
    db: Session, manager: User, cashier: User
) -> None:
    beans = _ingredient(db, "Coffee beans", Unit.G, qty="1000", cost="400")
    coffee = make_menu_item(db, product_type=ProductType.PREPARED)
    _version(db, manager, coffee.id, [(beans.id, "18")])
    order = _open(db, cashier, (coffee.id, "1"))

    ordering.cancel_order(
        db,
        order_id=order.id,
        data=OrderCancel(reason="customer left"),
        actor=cashier,
    )

    assert _sale_movements(db, order.id) == []
    assert balance_of(db, beans.id).quantity == D("1000.0000")


def test_duplicate_completion_does_not_deduct_twice(
    db: Session, manager: User, cashier: User
) -> None:
    beans = _ingredient(db, "Coffee beans", Unit.G, qty="1000", cost="400")
    coffee = make_menu_item(db, product_type=ProductType.PREPARED)
    _version(db, manager, coffee.id, [(beans.id, "18")])
    order = _open(db, cashier, (coffee.id, "1"))
    _pay(db, cashier, order.id)

    ordering.complete_order(
        db, order_id=order.id, actor=cashier, idempotency_key="once"
    )
    with pytest.raises(InvalidTransition):
        ordering.complete_order(
            db, order_id=order.id, actor=cashier, idempotency_key="again"
        )

    assert len(_sale_movements(db, order.id)) == 1
    assert balance_of(db, beans.id).quantity == D("982.0000")


def test_completion_rolls_back_when_audit_fails(
    db: Session, manager: User, cashier: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    beans = _ingredient(db, "Coffee beans", Unit.G, qty="100", cost="400")
    coffee = make_menu_item(db, product_type=ProductType.PREPARED)
    _version(db, manager, coffee.id, [(beans.id, "18")])
    order = _open(db, cashier, (coffee.id, "1"))
    _pay(db, cashier, order.id)
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
    stored = db.get(Order, order.id)
    assert stored is not None and stored.status == OrderStatus.PAID
    assert balance_of(db, beans.id).quantity == D("100.0000")


def test_line_cogs_reconciles_with_sale_movement_values(
    db: Session, manager: User, cashier: User
) -> None:
    beans = _ingredient(db, "Coffee beans", Unit.G, qty="1000", cost="400")
    milk = _ingredient(db, "Milk", Unit.ML, qty="1000", cost="15.5")
    iced = make_menu_item(db, product_type=ProductType.PREPARED)
    hot = make_menu_item(db, product_type=ProductType.PREPARED)
    _version(db, manager, iced.id, [(beans.id, "18"), (milk.id, "30")])
    _version(db, manager, hot.id, [(beans.id, "20")])
    order = _open(db, cashier, (iced.id, "2"), (hot.id, "1"))
    _pay(db, cashier, order.id)
    ordering.complete_order(
        db, order_id=order.id, actor=cashier, idempotency_key=uuid.uuid4().hex
    )

    lines = ordering._lines(db, order.id)
    movements = _sale_movements(db, order.id)
    allocations = db.exec(
        select(func.coalesce(func.sum(MovementAllocation.value), 0))
        .join(OrderLine, col(OrderLine.id) == col(MovementAllocation.order_line_id))
        .where(OrderLine.order_id == order.id)
    ).one()
    cogs = sum((line.cogs_amount or D("0") for line in lines), D("0"))
    movement_value = sum((movement.value for movement in movements), D("0"))

    assert cogs == -movement_value
    assert D(allocations) == movement_value


def _return(
    db: Session, actor: User, order_id: uuid.UUID, line_id: uuid.UUID, **kwargs
):
    return service.return_to_stock(
        db,
        order_id=order_id,
        data=StockReturnCreate(
            reason=kwargs.get("reason", "unopened"),
            lines=[
                StockReturnLineCreate(
                    order_line_id=line_id,
                    quantity=D(kwargs.get("quantity", "1")),
                    sellable=kwargs.get("sellable", True),
                )
            ],
        ),
        actor=actor,
        idempotency_key=kwargs.get("key", uuid.uuid4().hex),
    )


def test_sellable_bottle_return_posts_a_movement_at_original_cost(
    db: Session, manager: User, cashier: User
) -> None:
    bottle = _ingredient(db, "Aquafina 500ml", Unit.BOTTLE, qty="10", cost="5000")
    water = make_menu_item(db, product_type=ProductType.DIRECT_SALE)
    _version(db, manager, water.id, [(bottle.id, "1")])
    order = _open(db, cashier, (water.id, "1"))
    _pay(db, cashier, order.id)
    ordering.complete_order(
        db, order_id=order.id, actor=cashier, idempotency_key=uuid.uuid4().hex
    )
    line = ordering._lines(db, order.id)[0]

    result = _return(db, manager, order.id, line.id)

    assert result.status_code == 201
    [returned] = result.body["lines"]
    assert returned["sellable"] is True
    [movement] = db.exec(
        select(InventoryMovement).where(
            InventoryMovement.movement_type == MovementType.RETURN,
            InventoryMovement.source_id == order.id,
        )
    ).all()
    assert movement.quantity == D("1.0000")
    assert movement.unit_cost == D("5000.0000")
    assert movement.id == uuid.UUID(returned["movement_id"])
    assert balance_of(db, bottle.id).quantity == D("10.0000")
    assert_reconciled(db, bottle.id)


def test_prepared_item_cannot_be_returned_to_stock(
    db: Session, manager: User, cashier: User
) -> None:
    beans = _ingredient(db, "Coffee beans", Unit.G, qty="100", cost="400")
    coffee = make_menu_item(db, product_type=ProductType.PREPARED)
    _version(db, manager, coffee.id, [(beans.id, "18")])
    order = _open(db, cashier, (coffee.id, "1"))
    _pay(db, cashier, order.id)
    ordering.complete_order(
        db, order_id=order.id, actor=cashier, idempotency_key=uuid.uuid4().hex
    )
    line = ordering._lines(db, order.id)[0]

    with pytest.raises(PreparedReturnRejected):
        _return(db, manager, order.id, line.id)
    assert balance_of(db, beans.id).quantity == D("82.0000")


def test_return_is_capped_and_idempotent(
    db: Session, manager: User, cashier: User
) -> None:
    bottle = _ingredient(db, "Aquafina 500ml", Unit.BOTTLE, qty="10", cost="5000")
    water = make_menu_item(db, product_type=ProductType.DIRECT_SALE)
    _version(db, manager, water.id, [(bottle.id, "1")])
    order = _open(db, cashier, (water.id, "1"))
    _pay(db, cashier, order.id)
    ordering.complete_order(
        db, order_id=order.id, actor=cashier, idempotency_key=uuid.uuid4().hex
    )
    line = ordering._lines(db, order.id)[0]

    first = _return(db, manager, order.id, line.id, key="return-1")
    second = _return(db, manager, order.id, line.id, key="return-1")
    assert first.body == second.body
    with pytest.raises(ReturnExceedsSold):
        _return(db, manager, order.id, line.id, key="return-2")
    returns = db.exec(
        select(func.count())
        .select_from(InventoryMovement)
        .where(
            InventoryMovement.movement_type == MovementType.RETURN,
            InventoryMovement.source_id == order.id,
        )
    ).one()
    assert returns == 1


def test_unsellable_return_does_not_post_a_movement(
    db: Session, manager: User, cashier: User
) -> None:
    bottle = _ingredient(db, "Aquafina 500ml", Unit.BOTTLE, qty="10", cost="5000")
    water = make_menu_item(db, product_type=ProductType.DIRECT_SALE)
    _version(db, manager, water.id, [(bottle.id, "1")])
    order = _open(db, cashier, (water.id, "1"))
    _pay(db, cashier, order.id)
    ordering.complete_order(
        db, order_id=order.id, actor=cashier, idempotency_key=uuid.uuid4().hex
    )
    line = ordering._lines(db, order.id)[0]

    result = _return(db, manager, order.id, line.id, sellable=False, reason="opened")

    assert result.body["lines"][0]["movement_id"] is None
    assert (
        db.exec(
            select(InventoryMovement).where(
                InventoryMovement.movement_type == MovementType.RETURN,
                InventoryMovement.source_id == order.id,
            )
        ).first()
        is None
    )
    assert balance_of(db, bottle.id).quantity == D("9.0000")
