import re
import uuid
from decimal import Decimal

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlmodel import Session, col, select

from app.modules.identity.roles import Role
from app.modules.inventory import service
from app.modules.inventory.errors import (
    BarcodeTaken,
    InvalidUnitConversion,
    ItemHasMovements,
    ItemInactive,
    NegativeStockNotAllowed,
)
from app.modules.inventory.models import (
    InventoryCategory,
    InventoryItem,
    InventoryMovement,
    ItemType,
    MovementType,
    Unit,
)
from app.modules.inventory.schemas import InventoryItemCreate, InventoryItemUpdate
from tests.utils.inventory import (
    any_inventory_category,
    assert_reconciled,
    balance_of,
    make_inventory_item,
    seed_stock,
)
from tests.utils.user import make_user_with_role
from tests.utils.utils import random_lower_string

D = Decimal

BAKERY_ITEMS = (
    "Trứng gà",
    "Bột mì",
    "Bột nở",
    "Siro",
    "Sữa tươi",
    "Đường",
    "Kem tươi whipping",
    "Muối",
    "Tinh chất vani",
    "Rượu rum",
)


def _create_payload(db: Session, **overrides: object) -> InventoryItemCreate:
    values: dict[str, object] = {
        "name": "Coffee beans",
        "category_id": any_inventory_category(db).id,
        "item_type": ItemType.INGREDIENT,
        "base_unit": Unit.G,
        "purchase_unit": Unit.KG,
        "conversion_factor": D("1000"),
        **overrides,
    }
    return InventoryItemCreate.model_validate(values)


def _post(
    db: Session, item_id: uuid.UUID, qty: str, cost: str | None = None, **kw: object
) -> list[InventoryMovement]:
    movements = service.post_movements(
        db,
        lines=[
            service.MovementLine(
                item_id=item_id,
                quantity=D(qty),
                unit_cost=None if cost is None else D(cost),
            )
        ],
        movement_type=MovementType.ADJUSTMENT,
        source_type="test",
        source_id=uuid.uuid4(),
        actor=None,
        **kw,  # type: ignore[arg-type]
    )
    db.commit()
    return movements


def test_seed_categories_exist(db: Session) -> None:
    names = {c.name for c in db.exec(select(InventoryCategory)).all()}
    assert {"Nguyên vật liệu", "Công cụ dụng cụ", "Hàng bán sẵn", "Bao bì"} <= names


def test_create_coffee_beans_with_zero_balance(db: Session) -> None:
    actor = make_user_with_role(db, Role.INVENTORY_STAFF)
    data = _create_payload(db)

    item = service.create_item(db, data=data, actor=actor)

    assert re.fullmatch(r"SP-\d{5,}", item.sku)
    assert item.base_unit == Unit.G and item.purchase_unit == Unit.KG
    assert item.conversion_factor == D("1000")
    assert item.quantity == 0 and item.avg_unit_cost == 0 and item.value == 0


def test_skus_are_sequential(db: Session) -> None:
    actor = make_user_with_role(db, Role.INVENTORY_STAFF)

    first, second = (
        service.create_item(db, data=_create_payload(db), actor=actor).sku
        for _ in range(2)
    )

    assert int(second.removeprefix("SP-")) == int(first.removeprefix("SP-")) + 1


def test_duplicate_barcode_conflicts(db: Session) -> None:
    actor = make_user_with_role(db, Role.INVENTORY_STAFF)
    existing = make_inventory_item(db, barcode=f"89{random_lower_string()[:10]}")

    with pytest.raises(BarcodeTaken):
        service.create_item(
            db, data=_create_payload(db, barcode=existing.barcode), actor=actor
        )


@pytest.mark.parametrize("sku", ["SKU-1", "SP-1", "sp-00001"])
def test_database_rejects_malformed_skus(db: Session, sku: str) -> None:
    with pytest.raises(IntegrityError, match="ck_inventory_items_sku_format"):
        make_inventory_item(db, sku=sku)


def test_bakery_starter_catalog_is_seeded(db: Session) -> None:
    items = db.exec(
        select(InventoryItem).where(col(InventoryItem.name).in_(BAKERY_ITEMS))
    ).all()

    assert {item.name for item in items} == set(BAKERY_ITEMS)
    for item in items:
        assert re.fullmatch(r"SP-\d{5,}", item.sku)
        assert item.item_type == ItemType.INGREDIENT and item.is_active
        assert balance_of(db, item.id).quantity == 0


@pytest.mark.parametrize("factor", ["0", "-5"])
def test_non_positive_factor_rejected_by_schema(db: Session, factor: str) -> None:
    with pytest.raises(ValueError):
        _create_payload(db, conversion_factor=D(factor))


def test_same_units_require_factor_one(db: Session) -> None:
    with pytest.raises(ValueError):
        _create_payload(db, purchase_unit=Unit.G, conversion_factor=D("2"))
    assert _create_payload(db, purchase_unit=Unit.G, conversion_factor=D("1"))


def test_update_rejects_invalid_unit_combination(db: Session) -> None:
    actor = make_user_with_role(db, Role.INVENTORY_STAFF)
    item = make_inventory_item(db)

    with pytest.raises(InvalidUnitConversion):
        service.update_item(
            db,
            item_id=item.id,
            data=InventoryItemUpdate(purchase_unit=Unit.G),
            actor=actor,
        )


def test_edit_cannot_change_quantity(db: Session) -> None:
    actor = make_user_with_role(db, Role.INVENTORY_STAFF)
    item = make_inventory_item(db)
    seed_stock(db, item, "500", "1")

    update = InventoryItemUpdate.model_validate(
        {"name": "Renamed", "quantity": "99999", "avg_unit_cost": "5"}
    )
    result = service.update_item(db, item_id=item.id, data=update, actor=actor)

    assert result.name == "Renamed"
    assert result.quantity == D("500") and result.avg_unit_cost == D("1")


def test_item_with_movements_cannot_be_deleted(db: Session) -> None:
    actor = make_user_with_role(db, Role.INVENTORY_STAFF)
    item = make_inventory_item(db)
    seed_stock(db, item, "10", "1")

    with pytest.raises(ItemHasMovements):
        service.delete_item(db, item_id=item.id, actor=actor)


def test_item_without_movements_can_be_deleted(db: Session) -> None:
    actor = make_user_with_role(db, Role.INVENTORY_STAFF)
    item = make_inventory_item(db)

    service.delete_item(db, item_id=item.id, actor=actor)

    assert service.search_items(db, q=item.sku)[1] == 0


def test_movements_reconcile_and_reaverage(db: Session) -> None:
    item = make_inventory_item(db)

    _post(db, item.id, "1000", "0.5")
    _post(db, item.id, "1000", "0.7")
    [out] = _post(db, item.id, "-18")

    balance = balance_of(db, item.id)
    assert balance.quantity == D("1982")
    assert balance.avg_unit_cost == D("0.6")
    assert balance.value == D("1189.20")
    assert out.unit_cost == D("0.6") and out.quantity_after == D("1982")
    assert_reconciled(db, item.id)


def test_movement_references_source(db: Session) -> None:
    item = make_inventory_item(db)
    source_id = uuid.uuid4()
    user = make_user_with_role(db, Role.INVENTORY_STAFF)

    [movement] = service.post_movements(
        db,
        lines=[
            service.MovementLine(item_id=item.id, quantity=D("5"), unit_cost=D("2"))
        ],
        movement_type=MovementType.RECEIPT,
        source_type="stock_receipt",
        source_id=source_id,
        actor=user,
    )

    assert (movement.source_type, movement.source_id) == ("stock_receipt", source_id)
    assert movement.actor_id == user.id
    assert movement.movement_type == MovementType.RECEIPT


def test_negative_stock_rejected_when_disallowed(db: Session) -> None:
    item = make_inventory_item(db)
    seed_stock(db, item, "5", "1")

    with pytest.raises(NegativeStockNotAllowed):
        _post(db, item.id, "-10", allow_negative=False)
    db.rollback()

    assert balance_of(db, item.id).quantity == D("5")
    assert_reconciled(db, item.id)


def test_negative_stock_allowed_flags_uncertain_cost(db: Session) -> None:
    item = make_inventory_item(db)
    seed_stock(db, item, "5", "1")

    [movement] = _post(db, item.id, "-10", allow_negative=True)

    assert movement.quantity_after == D("-5")
    assert movement.cost_uncertain is True
    assert service.search_items(db, q=item.sku, negative_stock=True)[1] == 1


def test_consuming_unknown_cost_is_flagged(db: Session) -> None:
    item = make_inventory_item(db)
    seed_stock(db, item, "100")

    [movement] = _post(db, item.id, "-10")

    assert movement.cost_uncertain is True


def test_inactive_item_rejected_for_new_movements(db: Session) -> None:
    item = make_inventory_item(db, is_active=False)

    with pytest.raises(ItemInactive):
        _post(db, item.id, "10", "1")


def test_movements_cannot_be_edited_or_deleted(db: Session) -> None:
    item = make_inventory_item(db)
    movement = seed_stock(db, item, "10", "1")

    with pytest.raises(DBAPIError, match="append-only"):
        with db.begin_nested():
            movement.quantity = D("20")
            db.add(movement)
            db.flush()
    with pytest.raises(DBAPIError, match="append-only"):
        with db.begin_nested():
            db.delete(movement)
            db.flush()


def test_low_stock_list(db: Session) -> None:
    tag = random_lower_string()[:8]
    milk = make_inventory_item(
        db,
        name=f"Milk {tag}",
        base_unit=Unit.ML,
        purchase_unit=Unit.L,
        min_stock=D("1000"),
    )
    plenty = make_inventory_item(db, name=f"Sugar {tag}", min_stock=D("100"))
    no_threshold = make_inventory_item(db, name=f"Cups {tag}")
    seed_stock(db, milk, "500", "0.03")
    seed_stock(db, plenty, "5000", "0.02")

    items, _ = service.search_items(db, q=tag, low_stock=True)

    assert [i.id for i in items] == [milk.id]
    assert items[0].is_low_stock is True
    assert no_threshold.id not in [i.id for i in items]


def test_movement_history_filter_and_running_balance(db: Session) -> None:
    item = make_inventory_item(db)
    seed_stock(db, item, "2000", "0.5")
    _post(db, item.id, "-100")
    _post(db, item.id, "-50")

    history, count = service.list_movements(db, item_id=item.id)
    assert count == 3
    assert [m.quantity_after for m in history] == [D("1850"), D("1900"), D("2000")]

    adjustments, count = service.list_movements(
        db, item_id=item.id, movement_type=MovementType.ADJUSTMENT
    )
    assert count == 2
    assert all(m.movement_type == MovementType.ADJUSTMENT for m in adjustments)
