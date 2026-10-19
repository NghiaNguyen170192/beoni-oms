import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlmodel import Session, select

from app.models import User
from app.modules.audit.models import AuditLog
from app.modules.catalog.models import MenuItem, ProductType
from app.modules.identity.roles import Role
from app.modules.inventory import service as inventory_service
from app.modules.inventory.errors import NegativeStockNotAllowed
from app.modules.inventory.models import (
    InventoryItem,
    InventoryMovement,
    InventoryRole,
    ItemType,
    MovementType,
    Unit,
)
from app.modules.production import service
from app.modules.production.errors import (
    BatchBackdatePermissionRequired,
    BatchHasDownstreamActivity,
    BatchNotDraft,
    InvalidBatchInput,
    InvalidBatchOutput,
)
from app.modules.production.models import (
    FinishedGoodLot,
    FinishedGoodLotMovement,
    ProductionBatch,
    ProductionBatchStatus,
)
from app.modules.production.schemas import (
    BatchIngredientActual,
    BatchIngredientCreate,
    BatchOutputActual,
    BatchOutputCreate,
    ProductionBatchComplete,
    ProductionBatchCreate,
    ProductionBatchPublic,
    ProductionBatchReverse,
    ProductionBatchUpdate,
)
from app.modules.recipes import service as recipe_service
from app.modules.recipes.schemas import (
    RecipeLineCreate,
    RecipeOutputLineCreate,
    RecipePublic,
    RecipeVersionCreate,
)
from tests.utils.catalog import make_menu_item
from tests.utils.inventory import balance_of, make_inventory_item, seed_stock
from tests.utils.user import make_user_with_role

D = Decimal


def _plan(
    ingredient_id: uuid.UUID,
    output_inventory_id: uuid.UUID,
    menu_item_id: uuid.UUID,
    *,
    planned_for: date = date(2026, 5, 10),
) -> ProductionBatchCreate:
    return ProductionBatchCreate(
        planned_for=planned_for,
        notes="Morning batch",
        ingredients=[
            BatchIngredientCreate(
                inventory_item_id=ingredient_id,
                planned_quantity=D("175"),
            )
        ],
        outputs=[
            BatchOutputCreate(
                menu_item_id=menu_item_id,
                inventory_item_id=output_inventory_id,
                planned_quantity=D("5"),
            )
        ],
    )


def _batch_inputs(
    db: Session,
) -> tuple[InventoryItem, InventoryItem, MenuItem]:
    ingredient = make_inventory_item(
        db,
        name="Custard mix",
        item_type=ItemType.INGREDIENT,
        role=InventoryRole.RAW_MATERIAL,
        base_unit=Unit.G,
        purchase_unit=Unit.G,
        conversion_factor=D("1"),
    )
    flan_stock = make_inventory_item(
        db,
        name="Flan stock",
        item_type=ItemType.MERCHANDISE,
        role=InventoryRole.FINISHED_GOOD,
        base_unit=Unit.PIECE,
        purchase_unit=Unit.PIECE,
        conversion_factor=D("1"),
    )
    flan = make_menu_item(db, name="Flan", product_type=ProductType.DIRECT_SALE)
    return ingredient, flan_stock, flan


def _create_batch(
    db: Session,
    actor: User,
    planned_for: date = date(2026, 5, 10),
) -> tuple[ProductionBatchPublic, InventoryItem, InventoryItem, MenuItem]:
    ingredient, flan_stock, flan = _batch_inputs(db)
    batch = service.create_batch(
        db,
        data=_plan(
            ingredient.id,
            flan_stock.id,
            flan.id,
            planned_for=planned_for,
        ),
        actor=actor,
    )
    return batch, ingredient, flan_stock, flan


def _create_formula(
    db: Session,
    actor: User,
    ingredient_id: uuid.UUID,
    output_inventory_id: uuid.UUID,
    menu_item_id: uuid.UUID,
    *,
    input_quantity: Decimal = D("175"),
    output_quantity: Decimal = D("5"),
    effective_from: datetime | None = None,
) -> RecipePublic:
    return recipe_service.create_version(
        db,
        data=RecipeVersionCreate(
            menu_item_id=menu_item_id,
            effective_from=effective_from or datetime(2026, 5, 1, tzinfo=timezone.utc),
            lines=[
                RecipeLineCreate(
                    inventory_item_id=ingredient_id,
                    quantity=input_quantity,
                )
            ],
            outputs=[
                RecipeOutputLineCreate(
                    menu_item_id=menu_item_id,
                    inventory_item_id=output_inventory_id,
                    quantity=output_quantity,
                )
            ],
        ),
        actor=actor,
    )


def test_create_batch_stores_planned_input_and_output_with_audit(
    db: Session,
) -> None:
    manager = make_user_with_role(db, Role.MANAGER)

    batch, ingredient, flan_stock, flan = _create_batch(db, manager)

    assert batch.status == ProductionBatchStatus.DRAFT
    assert batch.number > 0
    assert batch.recipe_id is None
    assert batch.ingredients[0].inventory_item_id == ingredient.id
    assert batch.ingredients[0].unit == Unit.G
    assert batch.ingredients[0].planned_quantity == D("175")
    assert batch.outputs[0].menu_item_id == flan.id
    assert batch.outputs[0].inventory_item_id == flan_stock.id
    assert batch.outputs[0].planned_quantity == D("5")
    audit_entry = db.exec(
        select(AuditLog).where(
            AuditLog.entity_type == "production_batch",
            AuditLog.entity_id == str(batch.id),
            AuditLog.action == "created",
        )
    ).one()
    assert audit_entry.actor_id == manager.id


def test_formula_selection_scales_inputs_and_uses_selected_outputs(
    db: Session,
) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    ingredient, flan_stock, flan = _batch_inputs(db)
    pudding_stock = make_inventory_item(
        db,
        name="Pudding stock",
        item_type=ItemType.MERCHANDISE,
        role=InventoryRole.FINISHED_GOOD,
        base_unit=Unit.PIECE,
        purchase_unit=Unit.PIECE,
        conversion_factor=D("1"),
    )
    pudding = make_menu_item(
        db, name="Pudding", product_type=ProductType.PREPARED
    )
    formula = recipe_service.create_version(
        db,
        data=RecipeVersionCreate(
            menu_item_id=flan.id,
            effective_from=datetime(2026, 5, 1, tzinfo=timezone.utc),
            lines=[
                RecipeLineCreate(
                    inventory_item_id=ingredient.id,
                    quantity=D("175"),
                )
            ],
            outputs=[
                RecipeOutputLineCreate(
                    menu_item_id=flan.id,
                    inventory_item_id=flan_stock.id,
                    quantity=D("5"),
                ),
                RecipeOutputLineCreate(
                    menu_item_id=pudding.id,
                    inventory_item_id=pudding_stock.id,
                    quantity=D("2"),
                ),
            ],
        ),
        actor=manager,
    )

    batch = service.create_batch(
        db,
        data=ProductionBatchCreate(
            planned_for=date(2026, 5, 10),
            recipe_id=formula.id,
            formula_runs=D("2"),
            outputs=[
                BatchOutputCreate(
                    menu_item_id=flan.id,
                    inventory_item_id=flan_stock.id,
                    planned_quantity=D("10"),
                ),
                BatchOutputCreate(
                    menu_item_id=pudding.id,
                    inventory_item_id=pudding_stock.id,
                    planned_quantity=D("3"),
                ),
            ],
        ),
        actor=manager,
    )

    assert batch.recipe_id == formula.id
    assert batch.formula_runs == D("2")
    assert batch.ingredients[0].planned_quantity == D("350")
    outputs_by_menu = {line.menu_item_id: line for line in batch.outputs}
    assert outputs_by_menu[flan.id].planned_quantity == D("10")
    assert outputs_by_menu[pudding.id].planned_quantity == D("3")

    pudding_only_batch = service.create_batch(
        db,
        data=ProductionBatchCreate(
            planned_for=date(2026, 5, 11),
            recipe_id=formula.id,
            formula_runs=D("1"),
            outputs=[
                BatchOutputCreate(
                    menu_item_id=pudding.id,
                    inventory_item_id=pudding_stock.id,
                    planned_quantity=D("8"),
                )
            ],
        ),
        actor=manager,
    )

    assert pudding_only_batch.ingredients[0].planned_quantity == D("175")
    assert len(pudding_only_batch.outputs) == 1
    assert pudding_only_batch.outputs[0].menu_item_id == pudding.id
    assert pudding_only_batch.outputs[0].planned_quantity == D("8")


def test_formula_draft_can_be_rescaled_without_mutating_the_formula(
    db: Session,
) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    ingredient, flan_stock, flan = _batch_inputs(db)
    formula = _create_formula(
        db, manager, ingredient.id, flan_stock.id, flan.id
    )
    batch = service.create_batch(
        db,
        data=ProductionBatchCreate(
            planned_for=date(2026, 5, 10),
            recipe_id=formula.id,
            formula_runs=D("2"),
            outputs=[
                BatchOutputCreate(
                    menu_item_id=flan.id,
                    inventory_item_id=flan_stock.id,
                    planned_quantity=D("6"),
                )
            ],
        ),
        actor=manager,
    )

    changed = service.update_batch(
        db,
        batch_id=batch.id,
        data=ProductionBatchUpdate(
            recipe_id=formula.id,
            formula_runs=D("3"),
            outputs=[
                BatchOutputCreate(
                    menu_item_id=flan.id,
                    inventory_item_id=flan_stock.id,
                    planned_quantity=D("15"),
                )
            ],
        ),
        actor=manager,
    )

    assert changed.recipe_id == formula.id
    assert changed.formula_runs == D("3")
    assert changed.ingredients[0].planned_quantity == D("525")
    assert changed.outputs[0].planned_quantity == D("15")
    assert formula.lines[0].quantity == D("175")
    assert formula.outputs[0].quantity == D("5")


def test_formula_batch_can_only_select_mapped_outputs(db: Session) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    ingredient, flan_stock, flan = _batch_inputs(db)
    formula = _create_formula(
        db, manager, ingredient.id, flan_stock.id, flan.id
    )
    other_stock = make_inventory_item(
        db,
        name="Other finished stock",
        item_type=ItemType.MERCHANDISE,
        role=InventoryRole.FINISHED_GOOD,
        base_unit=Unit.PIECE,
        purchase_unit=Unit.PIECE,
        conversion_factor=D("1"),
    )

    with pytest.raises(InvalidBatchOutput):
        service.create_batch(
            db,
            data=ProductionBatchCreate(
                planned_for=date(2026, 5, 10),
                recipe_id=formula.id,
                formula_runs=D("1"),
                outputs=[
                    BatchOutputCreate(
                        menu_item_id=flan.id,
                        inventory_item_id=other_stock.id,
                        planned_quantity=D("5"),
                    )
                ],
            ),
            actor=manager,
        )


def test_batch_keeps_its_formula_version_snapshot(db: Session) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    ingredient, flan_stock, flan = _batch_inputs(db)
    first_formula = _create_formula(
        db, manager, ingredient.id, flan_stock.id, flan.id
    )
    batch = service.create_batch(
        db,
        data=ProductionBatchCreate(
            planned_for=date(2026, 5, 10),
            recipe_id=first_formula.id,
            formula_runs=D("2"),
            outputs=[
                BatchOutputCreate(
                    menu_item_id=flan.id,
                    inventory_item_id=flan_stock.id,
                    planned_quantity=D("7"),
                )
            ],
        ),
        actor=manager,
    )
    _create_formula(
        db,
        manager,
        ingredient.id,
        flan_stock.id,
        flan.id,
        input_quantity=D("200"),
        output_quantity=D("4"),
        effective_from=datetime(2026, 5, 2, tzinfo=timezone.utc),
    )

    stored = service.get_batch(db, batch.id)

    assert stored.recipe_id == first_formula.id
    assert stored.formula_runs == D("2")
    assert stored.ingredients[0].planned_quantity == D("350")
    assert stored.outputs[0].planned_quantity == D("7")


def test_batch_list_filters_by_status_and_planned_date(db: Session) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    included, ingredient, _, flan = _create_batch(db, manager, date(2026, 5, 10))
    other_stock = make_inventory_item(
        db,
        name="Pudding stock",
        item_type=ItemType.MERCHANDISE,
        role=InventoryRole.FINISHED_GOOD,
        base_unit=Unit.PIECE,
        purchase_unit=Unit.PIECE,
        conversion_factor=D("1"),
    )
    other_menu_item = make_menu_item(
        db, name="Pudding", product_type=ProductType.PREPARED
    )
    service.create_batch(
        db,
        data=_plan(
            ingredient.id,
            other_stock.id,
            other_menu_item.id,
            planned_for=date(2026, 5, 10),
        ),
        actor=manager,
    )
    _create_batch(db, manager, date(2026, 5, 11))

    batches, count = service.list_batches(
        db,
        status=ProductionBatchStatus.DRAFT,
        planned_from=date(2026, 5, 10),
        planned_to=date(2026, 5, 10),
        menu_item_id=flan.id,
    )

    assert count == 1
    assert [batch.id for batch in batches] == [included.id]


def test_update_batch_replaces_draft_plan_and_audits_changes(db: Session) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    batch, ingredient, flan_stock, flan = _create_batch(db, manager)
    changed = service.update_batch(
        db,
        batch_id=batch.id,
        data=ProductionBatchUpdate(
            planned_for=date(2026, 5, 12),
            notes="Evening batch",
            ingredients=[
                BatchIngredientCreate(
                    inventory_item_id=ingredient.id,
                    planned_quantity=D("200"),
                )
            ],
            outputs=[
                BatchOutputCreate(
                    menu_item_id=flan.id,
                    inventory_item_id=flan_stock.id,
                    planned_quantity=D("6"),
                )
            ],
        ),
        actor=manager,
    )

    assert changed.planned_for == date(2026, 5, 12)
    assert changed.notes == "Evening batch"
    assert changed.ingredients[0].planned_quantity == D("200")
    assert changed.outputs[0].planned_quantity == D("6")
    update_audit = db.exec(
        select(AuditLog).where(
            AuditLog.entity_type == "production_batch",
            AuditLog.entity_id == str(batch.id),
            AuditLog.action == "updated",
        )
    ).one()
    assert update_audit.changes["planned_for"]["new"] == "2026-05-12"
    assert update_audit.changes["outputs"]["new"][0]["planned_quantity"] == "6.0000"


def test_completed_batch_cannot_be_updated(db: Session) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    batch, *_ = _create_batch(db, manager)
    row = db.get(ProductionBatch, batch.id)
    assert row is not None
    row.status = ProductionBatchStatus.COMPLETED
    row.finished_at = datetime.now(timezone.utc)
    row.completed_by_id = manager.id
    db.add(row)
    db.commit()

    with pytest.raises(BatchNotDraft):
        service.update_batch(
            db,
            batch_id=batch.id,
            data=ProductionBatchUpdate(notes="Cannot edit posted history"),
            actor=manager,
        )


def test_complete_batch_posts_stock_and_keeps_cost_at_batch_level(
    db: Session,
) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    batch, ingredient, _, _ = _create_batch(db, manager)
    seed_stock(db, ingredient, "1000", unit_cost="2", actor=manager)
    finished_at = datetime(2026, 5, 11, 12, tzinfo=timezone.utc)

    completion_data = ProductionBatchComplete(
        finished_at=finished_at,
        ingredients=[
            BatchIngredientActual(
                line_id=batch.ingredients[0].id,
                actual_quantity=D("180"),
            )
        ],
        outputs=[
            BatchOutputActual(
                line_id=batch.outputs[0].id,
                actual_good_quantity=D("5"),
                waste_quantity=D("1"),
            )
        ],
    )
    completion_response = service.complete_batch(
        db,
        batch_id=batch.id,
        data=completion_data,
        actor=manager,
        idempotency_key="production-complete-once",
    )
    completed = ProductionBatchPublic.model_validate(completion_response.body)
    retry_response = service.complete_batch(
        db,
        batch_id=batch.id,
        data=completion_data,
        actor=manager,
        idempotency_key="production-complete-once",
    )

    assert retry_response.body == completion_response.body
    assert completed.status == ProductionBatchStatus.COMPLETED
    assert completed.finished_at == finished_at
    assert completed.total_material_cost == D("360.00")
    assert completed.cost_uncertain is False
    assert completed.ingredients[0].actual_quantity == D("180")
    assert completed.outputs[0].actual_good_quantity == D("5")
    assert completed.outputs[0].waste_quantity == D("1")
    assert completed.outputs[0].unit_cost is None
    assert completed.outputs[0].cost_uncertain is True

    movements = db.exec(
        select(InventoryMovement).where(
            InventoryMovement.source_type == "production_batch",
            InventoryMovement.source_id == batch.id,
        )
    ).all()
    input_movement = next(
        movement
        for movement in movements
        if movement.movement_type == MovementType.PRODUCTION_CONSUMPTION
    )
    output_movement = next(
        movement
        for movement in movements
        if movement.movement_type == MovementType.PRODUCTION_RECEIPT
    )
    assert input_movement.quantity == D("-180")
    assert input_movement.value == D("-360.00")
    assert output_movement.quantity == D("5")

    lot = db.exec(
        select(FinishedGoodLot).where(FinishedGoodLot.batch_id == batch.id)
    ).one()
    lot_movement = db.exec(
        select(FinishedGoodLotMovement).where(
            FinishedGoodLotMovement.lot_id == lot.id
        )
    ).one()
    assert lot.produced_quantity == D("5")
    assert lot.quantity_on_hand == D("5")
    assert lot.unit_cost is None
    assert lot_movement.movement_id == output_movement.id
    assert balance_of(db, ingredient.id).quantity == D("820")
    assert balance_of(db, output_movement.item_id).quantity == D("5")


def test_backdated_completion_requires_permission_and_leaves_key_unused(
    db: Session,
) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    inventory_staff = make_user_with_role(db, Role.INVENTORY_STAFF)
    batch, ingredient, *_ = _create_batch(db, manager)
    seed_stock(db, ingredient, "1000", unit_cost="2", actor=manager)
    completion_data = ProductionBatchComplete(
        finished_at=datetime.now(timezone.utc) - timedelta(days=2),
        ingredients=[
            BatchIngredientActual(
                line_id=batch.ingredients[0].id,
                actual_quantity=D("180"),
            )
        ],
        outputs=[
            BatchOutputActual(
                line_id=batch.outputs[0].id,
                actual_good_quantity=D("5"),
            )
        ],
    )

    with pytest.raises(BatchBackdatePermissionRequired):
        service.complete_batch(
            db,
            batch_id=batch.id,
            data=completion_data,
            actor=inventory_staff,
            idempotency_key="production-backdated-completion",
        )

    assert balance_of(db, ingredient.id).quantity == D("1000")
    completed = service.complete_batch(
        db,
        batch_id=batch.id,
        data=completion_data,
        actor=manager,
        idempotency_key="production-backdated-completion",
    )
    assert ProductionBatchPublic.model_validate(completed.body).status == (
        ProductionBatchStatus.COMPLETED
    )


def test_complete_batch_rejects_insufficient_raw_materials(db: Session) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    batch, *_ = _create_batch(db, manager)

    with pytest.raises(NegativeStockNotAllowed):
        service.complete_batch(
            db,
            batch_id=batch.id,
            data=ProductionBatchComplete(
                ingredients=[
                    BatchIngredientActual(
                        line_id=batch.ingredients[0].id,
                        actual_quantity=D("1"),
                    )
                ],
                outputs=[
                    BatchOutputActual(
                        line_id=batch.outputs[0].id,
                        actual_good_quantity=D("1"),
                    )
                ],
            ),
            actor=manager,
            idempotency_key="production-shortage",
        )

    db.rollback()
    stored = db.get(ProductionBatch, batch.id)
    assert stored is not None
    assert stored.status == ProductionBatchStatus.DRAFT
    assert not db.exec(
        select(InventoryMovement).where(
            InventoryMovement.source_type == "production_batch",
            InventoryMovement.source_id == batch.id,
        )
    ).all()


def test_complete_batch_flags_uncertain_material_cost(db: Session) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    batch, ingredient, *_ = _create_batch(db, manager)
    seed_stock(db, ingredient, "1000", actor=manager)

    completion_response = service.complete_batch(
        db,
        batch_id=batch.id,
        data=ProductionBatchComplete(
            ingredients=[
                BatchIngredientActual(
                    line_id=batch.ingredients[0].id,
                    actual_quantity=D("175"),
                )
            ],
            outputs=[
                BatchOutputActual(
                    line_id=batch.outputs[0].id,
                    actual_good_quantity=D("5"),
                )
            ],
        ),
        actor=manager,
        idempotency_key="production-uncertain-cost",
    )
    completed = ProductionBatchPublic.model_validate(completion_response.body)

    assert completed.total_material_cost == D("0.00")
    assert completed.cost_uncertain is True


def test_reverse_unused_batch_restores_inventory_and_is_idempotent(
    db: Session,
) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    batch, ingredient, output_stock, _ = _create_batch(db, manager)
    seed_stock(db, ingredient, "1000", unit_cost="2", actor=manager)
    completion_data = ProductionBatchComplete(
        ingredients=[
            BatchIngredientActual(
                line_id=batch.ingredients[0].id,
                actual_quantity=D("180"),
            )
        ],
        outputs=[
            BatchOutputActual(
                line_id=batch.outputs[0].id,
                actual_good_quantity=D("5"),
            )
        ],
    )
    service.complete_batch(
        db,
        batch_id=batch.id,
        data=completion_data,
        actor=manager,
        idempotency_key="production-reverse-complete",
    )

    reversal_data = ProductionBatchReverse(reason="Wrong production record")
    reversal_response = service.reverse_batch(
        db,
        batch_id=batch.id,
        data=reversal_data,
        actor=manager,
        idempotency_key="production-reverse-once",
    )
    reversed_batch = ProductionBatchPublic.model_validate(reversal_response.body)
    retry_response = service.reverse_batch(
        db,
        batch_id=batch.id,
        data=reversal_data,
        actor=manager,
        idempotency_key="production-reverse-once",
    )

    assert retry_response.body == reversal_response.body
    assert reversed_batch.status == ProductionBatchStatus.REVERSED
    assert reversed_batch.reversal_reason == "Wrong production record"
    assert balance_of(db, ingredient.id).quantity == D("1000")
    assert balance_of(db, output_stock.id).quantity == D("0")
    lot = db.exec(
        select(FinishedGoodLot).where(FinishedGoodLot.batch_id == batch.id)
    ).one()
    assert lot.quantity_on_hand == D("0")
    original_movements = db.exec(
        select(InventoryMovement).where(
            InventoryMovement.source_type == "production_batch",
            InventoryMovement.source_id == batch.id,
        )
    ).all()
    reversal_movements = db.exec(
        select(InventoryMovement).where(
            InventoryMovement.source_type == "production_batch_reversal",
            InventoryMovement.source_id == batch.id,
        )
    ).all()
    assert {
        movement.item_id: movement.cost_uncertain for movement in reversal_movements
    } == {movement.item_id: movement.cost_uncertain for movement in original_movements}


def test_reverse_batch_rejects_output_with_downstream_movement(
    db: Session,
) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    batch, ingredient, output_stock, _ = _create_batch(db, manager)
    seed_stock(db, ingredient, "1000", unit_cost="2", actor=manager)
    completed = service.complete_batch(
        db,
        batch_id=batch.id,
        data=ProductionBatchComplete(
            ingredients=[
                BatchIngredientActual(
                    line_id=batch.ingredients[0].id,
                    actual_quantity=D("180"),
                )
            ],
            outputs=[
                BatchOutputActual(
                    line_id=batch.outputs[0].id,
                    actual_good_quantity=D("5"),
                )
            ],
        ),
        actor=manager,
        idempotency_key="production-downstream-complete",
    )
    assert completed.status_code == 200
    lot = db.exec(
        select(FinishedGoodLot).where(FinishedGoodLot.batch_id == batch.id)
    ).one()
    [sale_movement] = inventory_service.post_movements(
        db,
        lines=[inventory_service.MovementLine(item_id=output_stock.id, quantity=D("-1"))],
        movement_type=MovementType.SALE_CONSUMPTION,
        source_type="test_sale",
        source_id=uuid.uuid4(),
        actor=manager,
    )
    lot.quantity_on_hand = D("4")
    db.add(lot)
    db.add(
        FinishedGoodLotMovement(
            lot_id=lot.id,
            movement_id=sale_movement.id,
            quantity=D("-1"),
        )
    )
    db.commit()

    with pytest.raises(BatchHasDownstreamActivity):
        service.reverse_batch(
            db,
            batch_id=batch.id,
            data=ProductionBatchReverse(reason="Attempt unsafe reversal"),
            actor=manager,
            idempotency_key="production-unsafe-reverse",
        )

    stored = db.get(ProductionBatch, batch.id)
    assert stored is not None
    assert stored.status == ProductionBatchStatus.COMPLETED
    assert not db.exec(
        select(InventoryMovement).where(
            InventoryMovement.source_type == "production_batch_reversal",
            InventoryMovement.source_id == batch.id,
        )
    ).all()


def test_reverse_batch_rejects_untracked_output_adjustment(db: Session) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    batch, ingredient, output_stock, _ = _create_batch(db, manager)
    seed_stock(db, ingredient, "1000", unit_cost="2", actor=manager)
    service.complete_batch(
        db,
        batch_id=batch.id,
        data=ProductionBatchComplete(
            ingredients=[
                BatchIngredientActual(
                    line_id=batch.ingredients[0].id,
                    actual_quantity=D("180"),
                )
            ],
            outputs=[
                BatchOutputActual(
                    line_id=batch.outputs[0].id,
                    actual_good_quantity=D("5"),
                )
            ],
        ),
        actor=manager,
        idempotency_key="production-adjustment-complete",
    )
    inventory_service.post_movements(
        db,
        lines=[
            inventory_service.MovementLine(
                item_id=output_stock.id,
                quantity=D("-1"),
            )
        ],
        movement_type=MovementType.ADJUSTMENT,
        source_type="test_adjustment",
        source_id=uuid.uuid4(),
        actor=manager,
    )
    db.commit()

    with pytest.raises(BatchHasDownstreamActivity):
        service.reverse_batch(
            db,
            batch_id=batch.id,
            data=ProductionBatchReverse(reason="Attempt reversal after adjustment"),
            actor=manager,
            idempotency_key="production-adjustment-reverse",
        )

    stored = db.get(ProductionBatch, batch.id)
    assert stored is not None
    assert stored.status == ProductionBatchStatus.COMPLETED
    assert not db.exec(
        select(InventoryMovement).where(
            InventoryMovement.source_type == "production_batch_reversal",
            InventoryMovement.source_id == batch.id,
        )
    ).all()


def test_batch_inputs_must_be_raw_materials(db: Session) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    ingredient, flan_stock, flan = _batch_inputs(db)
    ingredient.role = InventoryRole.GENERAL
    db.add(ingredient)
    db.commit()

    with pytest.raises(InvalidBatchInput):
        service.create_batch(
            db,
            data=_plan(ingredient.id, flan_stock.id, flan.id),
            actor=manager,
        )
