"""Finished-goods lot factories shared by sale, return, and concurrency tests."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlmodel import Session, select

from app.models import User
from app.modules.catalog.models import MenuItem, ProductType
from app.modules.inventory.models import InventoryItem, InventoryRole, ItemType, Unit
from app.modules.production import service as production
from app.modules.production.models import FinishedGoodLot, ProductionBatch
from app.modules.production.schemas import (
    BatchIngredientActual,
    BatchIngredientCreate,
    BatchOutputActual,
    BatchOutputCreate,
    ProductionBatchComplete,
    ProductionBatchCreate,
)
from tests.utils.catalog import make_menu_item
from tests.utils.inventory import make_inventory_item, seed_stock

D = Decimal


def make_finished_good(
    db: Session, *, name: str = "Flan stock", unit: Unit = Unit.PIECE
) -> InventoryItem:
    """An inventory item classified to hold sellable finished-goods lots."""
    return make_inventory_item(
        db,
        name=name,
        item_type=ItemType.MERCHANDISE,
        role=InventoryRole.FINISHED_GOOD,
        base_unit=unit,
        purchase_unit=unit,
        conversion_factor=D("1"),
    )


def make_lot(
    db: Session,
    actor: User,
    *,
    menu_item: MenuItem | None = None,
    finished_good: InventoryItem | None = None,
    good: Decimal = D("5"),
    finished_at: datetime | None = None,
    ingredient_quantity: Decimal = D("175"),
) -> tuple[ProductionBatch, InventoryItem, InventoryItem, FinishedGoodLot]:
    """Complete a batch and return (batch, raw material, finished good, lot)."""
    ingredient = make_inventory_item(
        db,
        name="Custard mix",
        item_type=ItemType.INGREDIENT,
        role=InventoryRole.RAW_MATERIAL,
        base_unit=Unit.G,
        purchase_unit=Unit.G,
        conversion_factor=D("1"),
    )
    seed_stock(db, ingredient, "10000", unit_cost="2", actor=actor)
    finished_good = finished_good or make_finished_good(db)
    menu_item = menu_item or make_menu_item(
        db, name="Flan", product_type=ProductType.DIRECT_SALE
    )
    finished_at = finished_at or datetime(2026, 5, 11, 12, tzinfo=timezone.utc)

    batch = production.create_batch(
        db,
        data=ProductionBatchCreate(
            planned_for=finished_at.date(),
            notes="test lot",
            ingredients=[
                BatchIngredientCreate(
                    inventory_item_id=ingredient.id,
                    planned_quantity=ingredient_quantity,
                )
            ],
            outputs=[
                BatchOutputCreate(
                    menu_item_id=menu_item.id,
                    inventory_item_id=finished_good.id,
                    planned_quantity=good,
                )
            ],
        ),
        actor=actor,
    )
    production.complete_batch(
        db,
        batch_id=batch.id,
        data=ProductionBatchComplete(
            finished_at=finished_at,
            ingredients=[
                BatchIngredientActual(
                    line_id=batch.ingredients[0].id,
                    actual_quantity=ingredient_quantity,
                )
            ],
            outputs=[
                BatchOutputActual(
                    line_id=batch.outputs[0].id,
                    actual_good_quantity=good,
                )
            ],
        ),
        actor=actor,
        idempotency_key=f"test-lot-{uuid.uuid4().hex}",
    )
    lot = db.exec(
        select(FinishedGoodLot).where(FinishedGoodLot.batch_id == batch.id)
    ).one()
    return batch, ingredient, finished_good, lot
