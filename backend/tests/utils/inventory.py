import uuid
from decimal import Decimal
from typing import Any

from sqlmodel import Session, func, select

from app.models import User
from app.modules.inventory import service
from app.modules.inventory.models import (
    InventoryBalance,
    InventoryCategory,
    InventoryItem,
    InventoryMovement,
    ItemType,
    MovementType,
    Unit,
)
from tests.utils.utils import random_code, random_lower_string

TEST_SOURCE = "test_seed"


def any_inventory_category(db: Session) -> InventoryCategory:
    category = db.exec(select(InventoryCategory)).first()
    assert category is not None, "seed categories missing"
    return category


def make_inventory_item(db: Session, **overrides: Any) -> InventoryItem:
    values: dict[str, Any] = {
        "sku": random_code("SP-"),
        "name": f"Item {random_lower_string()[:10]}",
        "category_id": any_inventory_category(db).id,
        "item_type": ItemType.INGREDIENT,
        "base_unit": Unit.G,
        "purchase_unit": Unit.KG,
        "conversion_factor": Decimal("1000"),
        **overrides,
    }
    item = InventoryItem(**values)
    db.add(item)
    db.flush()
    db.add(InventoryBalance(item_id=item.id))
    db.commit()
    db.refresh(item)
    return item


def seed_stock(
    db: Session,
    item: InventoryItem,
    quantity: Decimal | str,
    unit_cost: Decimal | str | None = None,
    actor: User | None = None,
) -> InventoryMovement:
    """Post one movement directly (as a receipt would) and commit."""
    [movement] = service.post_movements(
        db,
        lines=[
            service.MovementLine(
                item_id=item.id,
                quantity=Decimal(quantity),
                unit_cost=None if unit_cost is None else Decimal(unit_cost),
            )
        ],
        movement_type=MovementType.RECEIPT,
        source_type=TEST_SOURCE,
        source_id=uuid.uuid4(),
        actor=actor,
        allow_negative=True,
    )
    db.commit()
    return movement


def balance_of(db: Session, item_id: uuid.UUID) -> InventoryBalance:
    balance = db.get(InventoryBalance, item_id, populate_existing=True)
    assert balance is not None
    return balance


def movement_sum(db: Session, item_id: uuid.UUID) -> Decimal:
    total = db.exec(
        select(func.coalesce(func.sum(InventoryMovement.quantity), 0)).where(
            InventoryMovement.item_id == item_id
        )
    ).one()
    return Decimal(total)


def assert_reconciled(db: Session, item_id: uuid.UUID) -> None:
    assert balance_of(db, item_id).quantity == movement_sum(db, item_id)
