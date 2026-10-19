import uuid
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal, localcontext
from typing import Any
from zoneinfo import ZoneInfo

from sqlmodel import Session, col, func, or_, select

from app.core.errors import Invalid
from app.core.money import money, quantity
from app.models import User, get_datetime_utc
from app.modules.audit import service as audit
from app.modules.catalog.models import MenuItem, ProductType
from app.modules.idempotency import service as idempotency
from app.modules.idempotency.service import StoredResponse
from app.modules.identity.permissions import Permission, has_permission
from app.modules.inventory.errors import InventoryItemNotFound, ItemInactive
from app.modules.inventory.models import (
    InventoryItem,
    InventoryMovement,
    InventoryRole,
    MovementType,
)
from app.modules.inventory.service import (
    MovementLine,
    lock_balances,
    post_movements,
)
from app.modules.ordering.models import Order, OrderLine
from app.modules.production.errors import (
    BatchBackdatePermissionRequired,
    BatchHasDownstreamActivity,
    BatchMenuItemNotFound,
    BatchNotCompletable,
    BatchNotDraft,
    BatchNotFound,
    BatchNotReversible,
    BatchOutputMappingConflict,
    EmptyBatchUpdate,
    InvalidBatchCompletion,
    InvalidBatchInput,
    InvalidBatchOutput,
    InvalidProductionFormula,
)
from app.modules.production.models import (
    FinishedGoodLot,
    FinishedGoodLotAllocation,
    FinishedGoodLotMovement,
    FinishedGoodLotOrigin,
    ProductionBatch,
    ProductionBatchIngredientLine,
    ProductionBatchOutputLine,
    ProductionBatchStatus,
)
from app.modules.production.schemas import (
    BatchIngredientCreate,
    BatchOutputCreate,
    ProductionBatchComplete,
    ProductionBatchCreate,
    ProductionBatchPublic,
    ProductionBatchReverse,
    ProductionBatchTraceabilityPublic,
    ProductionBatchLotTracePublic,
    ProductionLotOrderTracePublic,
    ProductionLotReturnTracePublic,
    FinishedGoodAvailabilityPublic,
    FinishedGoodsAvailabilityPublic,
    ProductionBatchSummary,
    ProductionBatchUpdate,
)
from app.modules.recipes.errors import RecipeNotFound
from app.modules.recipes.models import Recipe, RecipeKind, RecipeLine, RecipeOutputLine
from app.modules.recipes.models import StockReturn, StockReturnLine
from app.modules.settings.service import get_settings


def _validated_ingredients(
    session: Session, lines: Sequence[BatchIngredientCreate]
) -> list[tuple[BatchIngredientCreate, InventoryItem]]:
    item_ids = {line.inventory_item_id for line in lines}
    items = session.exec(
        select(InventoryItem).where(col(InventoryItem.id).in_(item_ids))
    ).all()
    item_map = {item.id: item for item in items}
    if len(item_map) != len(item_ids):
        raise InventoryItemNotFound()
    validated: list[tuple[BatchIngredientCreate, InventoryItem]] = []
    for line in lines:
        item = item_map[line.inventory_item_id]
        if not item.is_active:
            raise ItemInactive(f"Inventory item {item.sku} is inactive")
        if item.role != InventoryRole.RAW_MATERIAL:
            raise InvalidBatchInput()
        validated.append((line, item))
    return validated


def _validated_outputs(
    session: Session,
    lines: Sequence[BatchOutputCreate],
    *,
    exclude_batch_id: uuid.UUID | None = None,
) -> list[tuple[BatchOutputCreate, MenuItem, InventoryItem]]:
    menu_item_ids = {line.menu_item_id for line in lines}
    menu_items = session.exec(
        select(MenuItem).where(col(MenuItem.id).in_(menu_item_ids))
    ).all()
    menu_item_map = {item.id: item for item in menu_items}
    if len(menu_item_map) != len(menu_item_ids):
        raise BatchMenuItemNotFound()

    inventory_item_ids = {line.inventory_item_id for line in lines}
    inventory_items = session.exec(
        select(InventoryItem).where(col(InventoryItem.id).in_(inventory_item_ids))
    ).all()
    inventory_item_map = {item.id: item for item in inventory_items}
    if len(inventory_item_map) != len(inventory_item_ids):
        raise InventoryItemNotFound()

    for line in lines:
        menu_item = menu_item_map[line.menu_item_id]
        inventory_item = inventory_item_map[line.inventory_item_id]
        if (
            not menu_item.is_active
            or menu_item.product_type == ProductType.NON_STOCK
            or not inventory_item.is_active
            or inventory_item.role != InventoryRole.FINISHED_GOOD
        ):
            raise InvalidBatchOutput()

    recipe_mappings = session.exec(
        select(RecipeOutputLine.menu_item_id, RecipeOutputLine.inventory_item_id)
        .where(col(RecipeOutputLine.menu_item_id).in_(menu_item_ids))
        .order_by(col(RecipeOutputLine.menu_item_id))
    ).all()
    batch_mapping_query = (
        select(
            ProductionBatchOutputLine.menu_item_id,
            ProductionBatchOutputLine.inventory_item_id,
        )
        .where(col(ProductionBatchOutputLine.menu_item_id).in_(menu_item_ids))
    )
    if exclude_batch_id is not None:
        batch_mapping_query = batch_mapping_query.where(
            ProductionBatchOutputLine.batch_id != exclude_batch_id
        )
    batch_mappings = session.exec(batch_mapping_query).all()
    established_mappings: dict[uuid.UUID, set[uuid.UUID]] = {}
    for menu_item_id, inventory_item_id in [*recipe_mappings, *batch_mappings]:
        established_mappings.setdefault(menu_item_id, set()).add(inventory_item_id)
    if any(
        line.menu_item_id in established_mappings
        and established_mappings[line.menu_item_id] != {line.inventory_item_id}
        for line in lines
    ):
        raise BatchOutputMappingConflict()

    return [
        (line, menu_item_map[line.menu_item_id], inventory_item_map[line.inventory_item_id])
        for line in lines
    ]


def _formula_plan(
    session: Session,
    recipe_id: uuid.UUID,
    formula_runs: Decimal,
    outputs: Sequence[BatchOutputCreate],
) -> tuple[list[BatchIngredientCreate], list[BatchOutputCreate]]:
    recipe = session.get(Recipe, recipe_id)
    if recipe is None:
        raise RecipeNotFound()
    if recipe.kind != RecipeKind.RECIPE:
        raise InvalidProductionFormula()
    ingredient_rows = session.exec(
        select(RecipeLine)
        .where(RecipeLine.recipe_id == recipe.id)
        .order_by(col(RecipeLine.inventory_item_id))
    ).all()
    output_rows = session.exec(
        select(RecipeOutputLine)
        .where(RecipeOutputLine.recipe_id == recipe.id)
        .order_by(col(RecipeOutputLine.menu_item_id))
    ).all()
    if not ingredient_rows or not output_rows or not outputs:
        raise InvalidProductionFormula()

    allowed_outputs = {
        line.menu_item_id: line.inventory_item_id for line in output_rows
    }
    if any(
        allowed_outputs.get(line.menu_item_id) != line.inventory_item_id
        for line in outputs
    ):
        raise InvalidBatchOutput()

    def scaled(value: Decimal) -> Decimal:
        with localcontext() as context:
            context.prec = 50
            result = quantity(value * formula_runs)
        if result <= 0 or result >= Decimal("100000000000000"):
            raise InvalidProductionFormula()
        return result

    return (
        [
            BatchIngredientCreate(
                inventory_item_id=line.inventory_item_id,
                planned_quantity=scaled(line.quantity),
            )
            for line in ingredient_rows
        ],
        list(outputs),
    )


def _validate_formula_outputs(
    session: Session,
    recipe_id: uuid.UUID,
    outputs: Sequence[BatchOutputCreate],
) -> None:
    recipe_outputs = session.exec(
        select(RecipeOutputLine).where(RecipeOutputLine.recipe_id == recipe_id)
    ).all()
    allowed_outputs = {
        line.menu_item_id: line.inventory_item_id for line in recipe_outputs
    }
    if not recipe_outputs or not outputs:
        raise InvalidProductionFormula()
    if any(
        allowed_outputs.get(line.menu_item_id) != line.inventory_item_id
        for line in outputs
    ):
        raise InvalidBatchOutput()


def _batch_summary(batch: ProductionBatch) -> ProductionBatchSummary:
    return ProductionBatchSummary.model_validate(batch.model_dump())


def _batch_public(
    session: Session, batch: ProductionBatch
) -> ProductionBatchPublic:
    ingredient_rows = session.exec(
        select(ProductionBatchIngredientLine, InventoryItem)
        .join(
            InventoryItem,
            col(InventoryItem.id)
            == col(ProductionBatchIngredientLine.inventory_item_id),
        )
        .where(ProductionBatchIngredientLine.batch_id == batch.id)
        .order_by(col(ProductionBatchIngredientLine.line_no))
    ).all()
    output_rows = session.exec(
        select(ProductionBatchOutputLine, MenuItem, InventoryItem)
        .join(
            MenuItem,
            col(MenuItem.id) == col(ProductionBatchOutputLine.menu_item_id),
        )
        .join(
            InventoryItem,
            col(InventoryItem.id)
            == col(ProductionBatchOutputLine.inventory_item_id),
        )
        .where(ProductionBatchOutputLine.batch_id == batch.id)
        .order_by(col(ProductionBatchOutputLine.line_no))
    ).all()
    return ProductionBatchPublic.model_validate(
        {
            **batch.model_dump(),
            "ingredients": [
                {
                    **line.model_dump(),
                    "item_sku": item.sku,
                    "item_name": item.name,
                }
                for line, item in ingredient_rows
            ],
            "outputs": [
                {
                    **line.model_dump(),
                    "menu_item_name": menu_item.name,
                    "menu_item_code": menu_item.code,
                    "item_sku": item.sku,
                    "item_name": item.name,
                }
                for line, menu_item, item in output_rows
            ],
        }
    )


def get_batch_traceability(
    session: Session, batch_id: uuid.UUID
) -> ProductionBatchTraceabilityPublic:
    batch = session.get(ProductionBatch, batch_id)
    if batch is None:
        raise BatchNotFound()
    lots = session.exec(
        select(FinishedGoodLot)
        .where(FinishedGoodLot.batch_id == batch.id)
        .order_by(col(FinishedGoodLot.output_line_id))
    ).all()
    lot_ids = {lot.id for lot in lots}
    allocations_by_lot: dict[
        uuid.UUID, list[tuple[FinishedGoodLotAllocation, OrderLine, Order]]
    ] = {}
    return_lines_by_allocation: dict[
        uuid.UUID, list[tuple[StockReturnLine, StockReturn]]
    ] = {}
    if lot_ids:
        allocation_rows = session.exec(
            select(FinishedGoodLotAllocation, FinishedGoodLot, OrderLine, Order)
            .join(
                FinishedGoodLotMovement,
                col(FinishedGoodLotMovement.id)
                == col(FinishedGoodLotAllocation.lot_movement_id),
            )
            .join(
                FinishedGoodLot,
                col(FinishedGoodLot.id) == col(FinishedGoodLotMovement.lot_id),
            )
            .join(
                OrderLine,
                col(OrderLine.id) == col(FinishedGoodLotAllocation.order_line_id),
            )
            .join(Order, col(Order.id) == col(OrderLine.order_id))
            .where(col(FinishedGoodLot.id).in_(lot_ids))
            .order_by(
                col(FinishedGoodLot.id),
                col(Order.completed_at),
                col(OrderLine.line_no),
                col(FinishedGoodLotAllocation.id),
            )
        ).all()
        for allocation, lot, order_line, order in allocation_rows:
            allocations_by_lot.setdefault(lot.id, []).append(
                (allocation, order_line, order)
            )
        returns = session.exec(
            select(StockReturnLine, StockReturn)
            .join(
                StockReturn,
                col(StockReturn.id) == col(StockReturnLine.stock_return_id),
            )
            .where(col(StockReturnLine.finished_good_lot_id).in_(lot_ids))
            .order_by(col(StockReturn.created_at), col(StockReturnLine.id))
        ).all()
        for return_line, stock_return in returns:
            if (
                return_line.finished_good_lot_allocation_id is not None
                and return_line.finished_good_lot_id is not None
            ):
                return_lines_by_allocation.setdefault(
                    return_line.finished_good_lot_allocation_id, []
                ).append((return_line, stock_return))

    trace_lots = []
    inventory_ids = {lot.inventory_item_id for lot in lots}
    inventory_by_id = {
        item.id: item
        for item in session.exec(
            select(InventoryItem).where(col(InventoryItem.id).in_(inventory_ids))
        ).all()
    }
    for lot in lots:
        order_traces = []
        for allocation, order_line, order in allocations_by_lot.get(lot.id, []):
            allocation_returns = return_lines_by_allocation.get(allocation.id, [])
            order_traces.append(
                ProductionLotOrderTracePublic(
                    order_id=order.id,
                    order_number=order.number,
                    order_status=order.status.value,
                    completed_at=order.completed_at,
                    order_line_id=order_line.id,
                    item_name=order_line.item_name,
                    allocated_quantity=allocation.quantity,
                    returned_quantity=quantity(
                        sum(
                            (entry[0].quantity for entry in allocation_returns),
                            Decimal("0"),
                        )
                    ),
                    returns=[
                        ProductionLotReturnTracePublic(
                            stock_return_line_id=row.id,
                            stock_return_id=stock_return.id,
                            order_line_id=order_line.id,
                            quantity=row.quantity,
                            sellable=row.sellable,
                            reason=stock_return.reason,
                            returned_at=stock_return.created_at,
                        )
                        for row, stock_return in allocation_returns
                    ],
                )
            )
        output_item = inventory_by_id[lot.inventory_item_id]
        trace_lots.append(
            ProductionBatchLotTracePublic(
                lot_id=lot.id,
                lot_number=lot.lot_number,
                inventory_item_id=lot.inventory_item_id,
                item_name=output_item.name,
                produced_quantity=lot.produced_quantity,
                quantity_on_hand=lot.quantity_on_hand,
                available_quantity=quantity(
                    lot.quantity_on_hand - lot.reserved_quantity
                ),
                finished_at=lot.finished_at,
                expiry_date=lot.expiry_date,
                orders=order_traces,
            )
        )
    return ProductionBatchTraceabilityPublic(
        batch=_batch_public(session, batch),
        lots=trace_lots,
    )


def list_batches(
    session: Session,
    *,
    status: ProductionBatchStatus | None = None,
    planned_from: date | None = None,
    planned_to: date | None = None,
    recipe_id: uuid.UUID | None = None,
    menu_item_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[ProductionBatchSummary], int]:
    if planned_from is not None and planned_to is not None and planned_from > planned_to:
        raise Invalid("planned_from must be on or before planned_to")
    conditions: list[Any] = []
    if status is not None:
        conditions.append(ProductionBatch.status == status)
    if planned_from is not None:
        conditions.append(ProductionBatch.planned_for >= planned_from)
    if planned_to is not None:
        conditions.append(ProductionBatch.planned_for <= planned_to)
    if recipe_id is not None:
        conditions.append(ProductionBatch.recipe_id == recipe_id)
    if menu_item_id is not None:
        matching_batch_ids = select(ProductionBatchOutputLine.batch_id).where(
            ProductionBatchOutputLine.menu_item_id == menu_item_id
        )
        conditions.append(col(ProductionBatch.id).in_(matching_batch_ids))

    count = session.exec(
        select(func.count()).select_from(ProductionBatch).where(*conditions)
    ).one()
    rows = session.exec(
        select(ProductionBatch)
        .where(*conditions)
        .order_by(
            col(ProductionBatch.planned_for).desc(),
            col(ProductionBatch.number).desc(),
        )
        .offset(skip)
        .limit(limit)
    ).all()
    return [_batch_summary(row) for row in rows], count


def list_finished_good_availability(session: Session) -> FinishedGoodsAvailabilityPublic:
    mappings = session.exec(
        select(RecipeOutputLine.menu_item_id, RecipeOutputLine.inventory_item_id)
    ).all()
    mappings.extend(
        session.exec(
            select(
                ProductionBatchOutputLine.menu_item_id,
                ProductionBatchOutputLine.inventory_item_id,
            )
        ).all()
    )
    inventory_ids_by_menu: dict[uuid.UUID, set[uuid.UUID]] = {}
    for menu_item_id, inventory_item_id in mappings:
        inventory_ids_by_menu.setdefault(menu_item_id, set()).add(inventory_item_id)
    if any(len(inventory_ids) > 1 for inventory_ids in inventory_ids_by_menu.values()):
        raise BatchOutputMappingConflict()
    if not inventory_ids_by_menu:
        return FinishedGoodsAvailabilityPublic(data=[])

    menu_items = session.exec(
        select(MenuItem).where(
            col(MenuItem.id).in_(inventory_ids_by_menu),
            MenuItem.is_active.is_(True),
            MenuItem.is_available.is_(True),
            MenuItem.product_type != ProductType.NON_STOCK,
        )
    ).all()
    item_ids = {
        next(iter(inventory_ids_by_menu[item.id]))
        for item in menu_items
    }
    inventory_items = session.exec(
        select(InventoryItem).where(col(InventoryItem.id).in_(item_ids))
    ).all()
    inventory_by_id = {item.id: item for item in inventory_items}
    if len(inventory_by_id) != len(item_ids):
        raise InventoryItemNotFound()

    available_by_item: dict[uuid.UUID, Decimal] = {}
    if item_ids:
        today = datetime.now(ZoneInfo(get_settings(session).timezone)).date()
        lots = session.exec(
            select(FinishedGoodLot).where(
                col(FinishedGoodLot.inventory_item_id).in_(item_ids),
                or_(
                    col(FinishedGoodLot.expiry_date).is_(None),
                    col(FinishedGoodLot.expiry_date) >= today,
                ),
            )
        ).all()
        for lot in lots:
            available_by_item[lot.inventory_item_id] = quantity(
                available_by_item.get(lot.inventory_item_id, Decimal("0"))
                + max(
                    Decimal("0"),
                    lot.quantity_on_hand - lot.reserved_quantity,
                )
            )

    data = []
    for menu_item in sorted(menu_items, key=lambda row: row.code):
        item_id = next(iter(inventory_ids_by_menu[menu_item.id]))
        item = inventory_by_id[item_id]
        data.append(
            FinishedGoodAvailabilityPublic(
                menu_item_id=menu_item.id,
                menu_item_name=menu_item.name,
                inventory_item_id=item.id,
                inventory_item_sku=item.sku,
                inventory_item_name=item.name,
                available_quantity=available_by_item.get(
                    item.id, Decimal("0")
                ),
                unit=item.base_unit,
            )
        )
    return FinishedGoodsAvailabilityPublic(data=data)


def get_batch(session: Session, batch_id: uuid.UUID) -> ProductionBatchPublic:
    batch = session.get(ProductionBatch, batch_id)
    if batch is None:
        raise BatchNotFound()
    return _batch_public(session, batch)


def _ingredient_snapshot(
    session: Session, batch_id: uuid.UUID
) -> list[dict[str, Any]]:
    lines = session.exec(
        select(ProductionBatchIngredientLine)
        .where(ProductionBatchIngredientLine.batch_id == batch_id)
        .order_by(col(ProductionBatchIngredientLine.line_no))
    ).all()
    return [
        {
            "id": line.id,
            "inventory_item_id": line.inventory_item_id,
            "unit": line.unit.value,
            "planned_quantity": line.planned_quantity,
            "actual_quantity": line.actual_quantity,
            "movement_id": line.movement_id,
        }
        for line in lines
    ]


def _output_snapshot(
    session: Session, batch_id: uuid.UUID
) -> list[dict[str, Any]]:
    lines = session.exec(
        select(ProductionBatchOutputLine)
        .where(ProductionBatchOutputLine.batch_id == batch_id)
        .order_by(col(ProductionBatchOutputLine.line_no))
    ).all()
    return [
        {
            "id": line.id,
            "menu_item_id": line.menu_item_id,
            "inventory_item_id": line.inventory_item_id,
            "unit": line.unit.value,
            "planned_quantity": line.planned_quantity,
            "actual_good_quantity": line.actual_good_quantity,
            "waste_quantity": line.waste_quantity,
            "movement_id": line.movement_id,
        }
        for line in lines
    ]


def create_batch(
    session: Session, *, data: ProductionBatchCreate, actor: User
) -> ProductionBatchPublic:
    if data.recipe_id is not None:
        assert data.formula_runs is not None and data.outputs is not None
        ingredient_plan, output_plan = _formula_plan(
            session, data.recipe_id, data.formula_runs, data.outputs
        )
    else:
        assert data.ingredients is not None and data.outputs is not None
        ingredient_plan, output_plan = data.ingredients, data.outputs
    ingredients = _validated_ingredients(session, ingredient_plan)
    outputs = _validated_outputs(session, output_plan)
    batch = ProductionBatch(
        planned_for=data.planned_for,
        notes=data.notes,
        created_by_id=actor.id,
        recipe_id=data.recipe_id,
        formula_runs=data.formula_runs,
    )
    session.add(batch)
    session.flush()
    session.add_all(
        [
            ProductionBatchIngredientLine(
                batch_id=batch.id,
                line_no=line_no,
                inventory_item_id=line.inventory_item_id,
                unit=item.base_unit,
                planned_quantity=quantity(line.planned_quantity),
            )
            for line_no, (line, item) in enumerate(ingredients, start=1)
        ]
    )
    session.add_all(
        [
            ProductionBatchOutputLine(
                batch_id=batch.id,
                line_no=line_no,
                menu_item_id=line.menu_item_id,
                inventory_item_id=line.inventory_item_id,
                unit=item.base_unit,
                planned_quantity=quantity(line.planned_quantity),
            )
            for line_no, (line, _, item) in enumerate(outputs, start=1)
        ]
    )
    session.flush()
    audit.record(
        session,
        actor=actor,
        entity_type="production_batch",
        entity_id=batch.id,
        action="created",
        changes={
            "planned_for": batch.planned_for,
            "recipe_id": batch.recipe_id,
            "formula_runs": batch.formula_runs,
            "ingredients": _ingredient_snapshot(session, batch.id),
            "outputs": _output_snapshot(session, batch.id),
        },
    )
    session.commit()
    session.refresh(batch)
    return _batch_public(session, batch)


def update_batch(
    session: Session,
    *,
    batch_id: uuid.UUID,
    data: ProductionBatchUpdate,
    actor: User,
) -> ProductionBatchPublic:
    batch = session.exec(
        select(ProductionBatch)
        .where(ProductionBatch.id == batch_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if batch is None:
        raise BatchNotFound()
    if batch.status != ProductionBatchStatus.DRAFT:
        raise BatchNotDraft()

    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise EmptyBatchUpdate()
    if "planned_for" in changes and data.planned_for is None:
        raise Invalid("planned_for cannot be null")
    for field in ("ingredients", "outputs"):
        if field in changes and changes[field] is None:
            raise Invalid(f"{field} cannot be null")

    old_state = {
        "planned_for": batch.planned_for,
        "notes": batch.notes,
        "recipe_id": batch.recipe_id,
        "formula_runs": batch.formula_runs,
        "ingredients": _ingredient_snapshot(session, batch.id),
        "outputs": _output_snapshot(session, batch.id),
    }

    formula_selected = "recipe_id" in changes
    if (
        batch.recipe_id is not None
        and "ingredients" in changes
        and not formula_selected
    ):
        raise Invalid(
            "Formula-based batch ingredients are controlled by the formula run count"
        )
    if formula_selected and data.recipe_id is not None:
        assert data.formula_runs is not None and data.outputs is not None
        ingredient_plan, output_plan = _formula_plan(
            session, data.recipe_id, data.formula_runs, data.outputs
        )
        ingredients_to_update: list[BatchIngredientCreate] | None = ingredient_plan
        outputs_to_update: list[BatchOutputCreate] | None = output_plan
    elif formula_selected:
        assert data.ingredients is not None and data.outputs is not None
        ingredients_to_update = data.ingredients
        outputs_to_update = data.outputs
    else:
        ingredients_to_update = data.ingredients
        outputs_to_update = data.outputs

    if (
        batch.recipe_id is not None
        and not formula_selected
        and outputs_to_update is not None
    ):
        _validate_formula_outputs(session, batch.recipe_id, outputs_to_update)

    validated_ingredients = (
        _validated_ingredients(session, ingredients_to_update)
        if ingredients_to_update is not None
        else None
    )
    validated_outputs = (
        _validated_outputs(
            session, outputs_to_update, exclude_batch_id=batch.id
        )
        if outputs_to_update is not None
        else None
    )

    if validated_ingredients is not None:
        old_lines = session.exec(
            select(ProductionBatchIngredientLine).where(
                ProductionBatchIngredientLine.batch_id == batch.id
            )
        ).all()
        for line in old_lines:
            session.delete(line)
        session.flush()
        session.add_all(
            [
                ProductionBatchIngredientLine(
                    batch_id=batch.id,
                    line_no=line_no,
                    inventory_item_id=line.inventory_item_id,
                    unit=item.base_unit,
                    planned_quantity=quantity(line.planned_quantity),
                )
                for line_no, (line, item) in enumerate(
                    validated_ingredients or [], start=1
                )
            ]
        )

    if validated_outputs is not None:
        old_lines = session.exec(
            select(ProductionBatchOutputLine).where(
                ProductionBatchOutputLine.batch_id == batch.id
            )
        ).all()
        for line in old_lines:
            session.delete(line)
        session.flush()
        session.add_all(
            [
                ProductionBatchOutputLine(
                    batch_id=batch.id,
                    line_no=line_no,
                    menu_item_id=line.menu_item_id,
                    inventory_item_id=line.inventory_item_id,
                    unit=item.base_unit,
                    planned_quantity=quantity(line.planned_quantity),
                )
                for line_no, (line, _, item) in enumerate(
                    validated_outputs or [], start=1
                )
            ]
        )

    if "planned_for" in changes:
        assert data.planned_for is not None
        batch.planned_for = data.planned_for
    if "notes" in changes:
        batch.notes = data.notes
    if formula_selected:
        batch.recipe_id = data.recipe_id
        batch.formula_runs = data.formula_runs
    batch.updated_at = get_datetime_utc()
    session.add(batch)
    session.flush()
    new_state = {
        "planned_for": batch.planned_for,
        "notes": batch.notes,
        "recipe_id": batch.recipe_id,
        "formula_runs": batch.formula_runs,
        "ingredients": _ingredient_snapshot(session, batch.id),
        "outputs": _output_snapshot(session, batch.id),
    }
    audit_fields = set(changes).intersection(new_state)
    if formula_selected:
        audit_fields.update({"formula_runs", "ingredients", "outputs"})
    audit.record(
        session,
        actor=actor,
        entity_type="production_batch",
        entity_id=batch.id,
        action="updated",
        changes=audit.diff(old_state, new_state, audit_fields),
    )
    session.commit()
    session.refresh(batch)
    return _batch_public(session, batch)


def _complete_batch(
    session: Session,
    *,
    batch_id: uuid.UUID,
    data: ProductionBatchComplete,
    actor: User,
) -> ProductionBatchPublic:
    batch = session.exec(
        select(ProductionBatch)
        .where(ProductionBatch.id == batch_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if batch is None:
        raise BatchNotFound()
    if batch.status != ProductionBatchStatus.DRAFT:
        raise BatchNotCompletable()
    if data.finished_at is not None:
        timezone = ZoneInfo(get_settings(session).timezone)
        finished_date = data.finished_at.astimezone(timezone).date()
        if (
            finished_date < datetime.now(timezone).date()
            and not has_permission(actor, Permission.PRODUCTION_BACKDATE)
        ):
            raise BatchBackdatePermissionRequired()

    ingredient_lines = session.exec(
        select(ProductionBatchIngredientLine)
        .where(ProductionBatchIngredientLine.batch_id == batch.id)
        .order_by(col(ProductionBatchIngredientLine.line_no))
        .with_for_update()
    ).all()
    output_lines = session.exec(
        select(ProductionBatchOutputLine)
        .where(ProductionBatchOutputLine.batch_id == batch.id)
        .order_by(col(ProductionBatchOutputLine.line_no))
        .with_for_update()
    ).all()
    ingredient_actuals = {line.line_id: line.actual_quantity for line in data.ingredients}
    output_actuals = {line.line_id: line for line in data.outputs}
    if (
        not ingredient_lines
        or not output_lines
        or set(ingredient_actuals) != {line.id for line in ingredient_lines}
        or set(output_actuals) != {line.id for line in output_lines}
    ):
        raise InvalidBatchCompletion()
    if not any(value > 0 for value in ingredient_actuals.values()) or not any(
        actual.actual_good_quantity > 0 or actual.waste_quantity > 0
        for actual in output_actuals.values()
    ):
        raise InvalidBatchCompletion()

    validated_ingredients = _validated_ingredients(
        session,
        [
            BatchIngredientCreate(
                inventory_item_id=line.inventory_item_id,
                planned_quantity=line.planned_quantity,
            )
            for line in ingredient_lines
        ],
    )
    if any(
        item.base_unit != line.unit
        for line, (_, item) in zip(ingredient_lines, validated_ingredients, strict=True)
    ):
        raise InvalidBatchInput()

    validated_outputs = _validated_outputs(
        session,
        [
            BatchOutputCreate(
                menu_item_id=line.menu_item_id,
                inventory_item_id=line.inventory_item_id,
                planned_quantity=line.planned_quantity,
            )
            for line in output_lines
        ],
        exclude_batch_id=batch.id,
    )
    if any(
        item.base_unit != line.unit
        for line, (_, _, item) in zip(output_lines, validated_outputs, strict=True)
    ):
        raise InvalidBatchOutput()

    ingredient_quantities = {
        line.id: ingredient_actuals[line.id] for line in ingredient_lines
    }
    output_movements_to_post = [
        (line, output_actuals[line.id].actual_good_quantity)
        for line in output_lines
        if output_actuals[line.id].actual_good_quantity > 0
    ]
    affected_item_ids = {
        line.inventory_item_id
        for line in ingredient_lines
        if ingredient_quantities[line.id] > 0
    }
    affected_item_ids.update(
        line.inventory_item_id for line, _ in output_movements_to_post
    )
    lock_balances(session, affected_item_ids)

    input_lines_to_post = [
        (line, ingredient_quantities[line.id])
        for line in ingredient_lines
        if ingredient_quantities[line.id] > 0
    ]
    input_movements = post_movements(
        session,
        lines=[
            MovementLine(item_id=line.inventory_item_id, quantity=-actual_quantity)
            for line, actual_quantity in input_lines_to_post
        ],
        movement_type=MovementType.PRODUCTION_CONSUMPTION,
        source_type="production_batch",
        source_id=batch.id,
        actor=actor,
    )
    input_movement_by_line = {
        line.id: movement
        for (line, _), movement in zip(
            input_lines_to_post, input_movements, strict=True
        )
    }
    material_cost = money(
        sum((-movement.value for movement in input_movements), Decimal("0"))
    )

    for line in ingredient_lines:
        line.actual_quantity = ingredient_quantities[line.id]
        movement = input_movement_by_line.get(line.id)
        line.movement_id = movement.id if movement is not None else None
        session.add(line)

    finished_at = data.finished_at or get_datetime_utc()
    output_movements = post_movements(
        session,
        lines=[
            MovementLine(
                item_id=line.inventory_item_id,
                quantity=actual_good_quantity,
            )
            for line, actual_good_quantity in output_movements_to_post
        ],
        movement_type=MovementType.PRODUCTION_RECEIPT,
        source_type="production_batch",
        source_id=batch.id,
        actor=actor,
    )
    assert batch.number is not None
    for (line, actual_good_quantity), movement in zip(
        output_movements_to_post, output_movements, strict=True
    ):
        actual = output_actuals[line.id]
        line.actual_good_quantity = actual.actual_good_quantity
        line.waste_quantity = actual.waste_quantity
        line.unit_cost = None
        line.cost_uncertain = True
        line.movement_id = movement.id
        session.add(line)
        lot = FinishedGoodLot(
            lot_number=f"PB-{batch.number}-{line.line_no}",
            origin=FinishedGoodLotOrigin.PRODUCTION,
            batch_id=batch.id,
            output_line_id=line.id,
            inventory_item_id=line.inventory_item_id,
            produced_quantity=actual_good_quantity,
            quantity_on_hand=actual_good_quantity,
            unit_cost=None,
            finished_at=finished_at,
        )
        session.add(lot)
        session.flush()
        session.add(
            FinishedGoodLotMovement(
                lot_id=lot.id,
                movement_id=movement.id,
                quantity=actual_good_quantity,
            )
        )

    for line in output_lines:
        actual = output_actuals[line.id]
        line.actual_good_quantity = actual.actual_good_quantity
        line.waste_quantity = actual.waste_quantity
        line.unit_cost = None
        line.cost_uncertain = True
        session.add(line)

    batch.status = ProductionBatchStatus.COMPLETED
    batch.finished_at = finished_at
    batch.completed_by_id = actor.id
    batch.total_material_cost = material_cost
    batch.cost_uncertain = any(movement.cost_uncertain for movement in input_movements)
    batch.updated_at = get_datetime_utc()
    session.add(batch)
    session.flush()
    audit.record(
        session,
        actor=actor,
        entity_type="production_batch",
        entity_id=batch.id,
        action="completed",
        changes={
            "status": {"old": ProductionBatchStatus.DRAFT.value, "new": batch.status.value},
            "finished_at": batch.finished_at,
            "total_material_cost": batch.total_material_cost,
            "cost_uncertain": batch.cost_uncertain,
            "ingredients": _ingredient_snapshot(session, batch.id),
            "outputs": _output_snapshot(session, batch.id),
        },
    )
    return _batch_public(session, batch)


def complete_batch(
    session: Session,
    *,
    batch_id: uuid.UUID,
    data: ProductionBatchComplete,
    actor: User,
    idempotency_key: str,
) -> StoredResponse:
    def operation() -> tuple[int, Any]:
        result = _complete_batch(
            session, batch_id=batch_id, data=data, actor=actor
        )
        return 200, result.model_dump(mode="json")

    return idempotency.execute(
        session,
        scope="production.batch.complete",
        key=idempotency_key,
        payload={"batch_id": str(batch_id), **data.model_dump(mode="json")},
        operation=operation,
    )


def allocate_finished_good_order_lines(
    session: Session, order: Order, lines: list[OrderLine], actor: User
) -> None:
    """Deduct mapped finished goods from FEFO/FIFO lots without consuming recipes."""
    from app.modules.recipes.errors import InsufficientStock, Shortage

    stock_lines = [line for line in lines if line.product_type.value != "non_stock"]
    menu_item_ids = {line.menu_item_id for line in stock_lines}
    mappings = session.exec(
        select(RecipeOutputLine.menu_item_id, RecipeOutputLine.inventory_item_id)
        .where(col(RecipeOutputLine.menu_item_id).in_(menu_item_ids))
    ).all()
    mappings.extend(
        session.exec(
            select(
                ProductionBatchOutputLine.menu_item_id,
                ProductionBatchOutputLine.inventory_item_id,
            ).where(col(ProductionBatchOutputLine.menu_item_id).in_(menu_item_ids))
        ).all()
    )
    inventory_ids_by_menu: dict[uuid.UUID, set[uuid.UUID]] = {}
    for menu_item_id, inventory_item_id in mappings:
        inventory_ids_by_menu.setdefault(menu_item_id, set()).add(inventory_item_id)
    if any(len(inventory_ids) > 1 for inventory_ids in inventory_ids_by_menu.values()):
        raise BatchOutputMappingConflict()

    inventory_id_by_menu = {
        menu_item_id: next(iter(inventory_ids))
        for menu_item_id, inventory_ids in inventory_ids_by_menu.items()
    }
    tracked_lines = {
        line.id: inventory_id_by_menu[line.menu_item_id]
        for line in stock_lines
        if line.menu_item_id in inventory_id_by_menu
    }
    tracked_item_ids = set(tracked_lines.values())

    inventory_items = session.exec(
        select(InventoryItem).where(col(InventoryItem.id).in_(tracked_item_ids))
    ).all()
    inventory_by_id = {item.id: item for item in inventory_items}
    if len(inventory_by_id) != len(tracked_item_ids):
        raise InventoryItemNotFound()
    if any(item.role != InventoryRole.FINISHED_GOOD for item in inventory_by_id.values()):
        raise InvalidBatchOutput()
    if tracked_item_ids:
        lock_balances(session, tracked_item_ids)
        timezone = ZoneInfo(get_settings(session).timezone)
        today = datetime.now(timezone).date()
        lots = session.exec(
            select(FinishedGoodLot)
            .where(
                col(FinishedGoodLot.inventory_item_id).in_(tracked_item_ids),
                col(FinishedGoodLot.quantity_on_hand)
                > col(FinishedGoodLot.reserved_quantity),
                or_(
                    col(FinishedGoodLot.expiry_date).is_(None),
                    col(FinishedGoodLot.expiry_date) >= today,
                ),
            )
            .order_by(
                col(FinishedGoodLot.inventory_item_id),
                col(FinishedGoodLot.expiry_date).asc().nulls_last(),
                col(FinishedGoodLot.finished_at),
                col(FinishedGoodLot.id),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        ).all()
    else:
        lots = []
    lots_by_item: dict[uuid.UUID, list[FinishedGoodLot]] = {}
    remaining_by_lot: dict[uuid.UUID, Decimal] = {}
    available_by_item: dict[uuid.UUID, Decimal] = {}
    for lot in lots:
        lots_by_item.setdefault(lot.inventory_item_id, []).append(lot)
        remaining_by_lot[lot.id] = quantity(
            lot.quantity_on_hand - lot.reserved_quantity
        )
        available_by_item[lot.inventory_item_id] = quantity(
            available_by_item.get(lot.inventory_item_id, Decimal("0"))
            + remaining_by_lot[lot.id]
        )

    planned: list[tuple[FinishedGoodLot, OrderLine, Decimal]] = []
    required_by_item: dict[uuid.UUID, Decimal] = {}
    for line in stock_lines:
        item_id = tracked_lines.get(line.id)
        if item_id is None:
            continue
        required = quantity(line.quantity)
        required_by_item[item_id] = quantity(
            required_by_item.get(item_id, Decimal("0")) + required
        )
        unfilled = required
        for lot in lots_by_item.get(item_id, []):
            available = remaining_by_lot[lot.id]
            if available <= 0:
                continue
            allocated = min(available, unfilled)
            planned.append((lot, line, allocated))
            remaining_by_lot[lot.id] = quantity(available - allocated)
            unfilled = quantity(unfilled - allocated)
            if unfilled <= 0:
                break
    shortages = [
        Shortage(
            item_id=item_id,
            item=inventory_by_id[item_id].name,
            sku=inventory_by_id[item_id].sku,
            required=required,
            available=available_by_item.get(item_id, Decimal("0")),
            unit=inventory_by_id[item_id].base_unit.value,
        )
        for item_id, required in sorted(required_by_item.items())
        if required > available_by_item.get(item_id, Decimal("0"))
    ]
    if shortages:
        raise InsufficientStock(shortages)

    item_ids = sorted(required_by_item)
    movements = post_movements(
        session,
        lines=[
            MovementLine(
                item_id=item_id,
                quantity=-required_by_item[item_id],
                preserve_cost_uncertainty=True,
            )
            for item_id in item_ids
        ],
        movement_type=MovementType.SALE_CONSUMPTION,
        source_type="order",
        source_id=order.id,
        actor=actor,
        require_active=False,
        allow_negative=False,
    )
    movement_by_item = {
        movement.item_id: movement for movement in movements
    }

    lot_movement_quantities: dict[tuple[uuid.UUID, uuid.UUID], Decimal] = {}
    allocations_by_lot_movement: dict[
        tuple[uuid.UUID, uuid.UUID], list[tuple[OrderLine, Decimal]]
    ] = {}
    now = get_datetime_utc()
    for lot, line, allocated in planned:
        lot.quantity_on_hand = quantity(lot.quantity_on_hand - allocated)
        lot.updated_at = now
        session.add(lot)
        key = (lot.id, lot.inventory_item_id)
        lot_movement_quantities[key] = quantity(
            lot_movement_quantities.get(key, Decimal("0")) - allocated
        )
        allocations_by_lot_movement.setdefault(key, []).append((line, allocated))

    for (lot_id, item_id), movement_quantity in lot_movement_quantities.items():
        movement = movement_by_item[item_id]
        lot_movement = FinishedGoodLotMovement(
            lot_id=lot_id,
            movement_id=movement.id,
            quantity=movement_quantity,
            created_at=movement.occurred_at,
        )
        session.add(lot_movement)
        session.flush()
        session.add_all(
            [
                FinishedGoodLotAllocation(
                    lot_movement_id=lot_movement.id,
                    order_line_id=line.id,
                    quantity=allocated,
                    created_at=movement.occurred_at,
                )
                for line, allocated in allocations_by_lot_movement[(lot_id, item_id)]
            ]
        )

    now = get_datetime_utc()
    for line in lines:
        line.recipe_version_id = None
        if line.product_type.value == "non_stock":
            line.cogs_amount = Decimal("0")
            line.cost_uncertain = False
        else:
            line.cogs_amount = None
            line.cost_uncertain = True
        line.updated_at = now
        session.add(line)
    session.flush()


def reverse_batch(
    session: Session,
    *,
    batch_id: uuid.UUID,
    data: ProductionBatchReverse,
    actor: User,
    idempotency_key: str,
) -> StoredResponse:
    def operation() -> tuple[int, Any]:
        batch = session.exec(
            select(ProductionBatch)
            .where(ProductionBatch.id == batch_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).first()
        if batch is None:
            raise BatchNotFound()
        if batch.status != ProductionBatchStatus.COMPLETED:
            raise BatchNotReversible()

        ingredient_lines = session.exec(
            select(ProductionBatchIngredientLine)
            .where(ProductionBatchIngredientLine.batch_id == batch.id)
            .order_by(col(ProductionBatchIngredientLine.line_no))
        ).all()
        output_lines = session.exec(
            select(ProductionBatchOutputLine)
            .where(ProductionBatchOutputLine.batch_id == batch.id)
            .order_by(col(ProductionBatchOutputLine.line_no))
        ).all()
        output_lines_with_stock = [
            line
            for line in output_lines
            if line.actual_good_quantity is not None
            and line.actual_good_quantity > 0
        ]
        input_lines_with_consumption = [
            line
            for line in ingredient_lines
            if line.actual_quantity is not None and line.actual_quantity > 0
        ]
        affected_item_ids = {
            line.inventory_item_id
            for line in [*input_lines_with_consumption, *output_lines_with_stock]
        }
        lock_balances(session, affected_item_ids)
        lots = session.exec(
            select(FinishedGoodLot)
            .where(FinishedGoodLot.batch_id == batch.id)
            .order_by(col(FinishedGoodLot.output_line_id))
            .with_for_update()
        ).all()
        lots_by_output_line = {lot.output_line_id: lot for lot in lots}
        if (
            len(lots) != len(output_lines_with_stock)
            or set(lots_by_output_line)
            != {line.id for line in output_lines_with_stock}
        ):
            raise BatchHasDownstreamActivity()

        lot_movements = session.exec(
            select(FinishedGoodLotMovement)
            .where(col(FinishedGoodLotMovement.lot_id).in_([lot.id for lot in lots]))
            .order_by(col(FinishedGoodLotMovement.lot_id))
            .with_for_update()
        ).all()
        movements_by_lot: dict[uuid.UUID, list[FinishedGoodLotMovement]] = {}
        for lot_movement in lot_movements:
            movements_by_lot.setdefault(lot_movement.lot_id, []).append(lot_movement)
        for lot in lots:
            lot_entries = movements_by_lot.get(lot.id, [])
            if (
                lot.quantity_on_hand != lot.produced_quantity
                or lot.reserved_quantity != 0
                or len(lot_entries) != 1
                or lot_entries[0].quantity != lot.produced_quantity
            ):
                raise BatchHasDownstreamActivity()
        lot_movement_ids = [movement.id for movement in lot_movements]
        if lot_movement_ids and session.exec(
            select(FinishedGoodLotAllocation.id)
            .where(
                col(FinishedGoodLotAllocation.lot_movement_id).in_(lot_movement_ids)
            )
            .limit(1)
        ).first():
            raise BatchHasDownstreamActivity()

        input_movement_ids = [line.movement_id for line in input_lines_with_consumption]
        output_movement_ids = [
            line.movement_id for line in output_lines_with_stock
        ]
        if (
            any(movement_id is None for movement_id in input_movement_ids)
            or any(movement_id is None for movement_id in output_movement_ids)
        ):
            raise BatchNotReversible()
        input_movement_ids = [
            movement_id
            for movement_id in input_movement_ids
            if movement_id is not None
        ]
        output_movement_ids = [
            movement_id for movement_id in output_movement_ids if movement_id is not None
        ]
        original_input_movements = session.exec(
            select(InventoryMovement).where(
                col(InventoryMovement.id).in_(input_movement_ids)
            )
        ).all()
        original_output_movements = session.exec(
            select(InventoryMovement).where(
                col(InventoryMovement.id).in_(output_movement_ids)
            )
        ).all()
        input_by_id = {movement.id: movement for movement in original_input_movements}
        output_by_id = {
            movement.id: movement for movement in original_output_movements
        }
        if (
            len(input_by_id) != len(input_movement_ids)
            or len(output_by_id) != len(output_movement_ids)
        ):
            raise BatchNotReversible()
        ordered_input_movements = [
            input_by_id[movement_id] for movement_id in input_movement_ids
        ]
        ordered_output_movements = [
            output_by_id[movement_id] for movement_id in output_movement_ids
        ]
        for line, movement in zip(
            input_lines_with_consumption, ordered_input_movements, strict=True
        ):
            if (
                movement.movement_type != MovementType.PRODUCTION_CONSUMPTION
                or movement.source_type != "production_batch"
                or movement.source_id != batch.id
                or line.actual_quantity is None
                or movement.quantity != -line.actual_quantity
                or movement.item_id != line.inventory_item_id
            ):
                raise BatchNotReversible()
        for line, movement in zip(
            output_lines_with_stock, ordered_output_movements, strict=True
        ):
            if (
                movement.movement_type != MovementType.PRODUCTION_RECEIPT
                or movement.source_type != "production_batch"
                or movement.source_id != batch.id
                or line.actual_good_quantity is None
                or movement.quantity != line.actual_good_quantity
                or movement.item_id != line.inventory_item_id
            ):
                raise BatchNotReversible()
        for movement in ordered_output_movements:
            later_movement_ids = set(
                session.exec(
                    select(InventoryMovement.id).where(
                        InventoryMovement.item_id == movement.item_id,
                        InventoryMovement.occurred_at >= movement.occurred_at,
                        InventoryMovement.id != movement.id,
                    )
                ).all()
            )
            if later_movement_ids:
                lot_linked_movement_ids = set(
                    session.exec(
                        select(FinishedGoodLotMovement.movement_id).where(
                            col(FinishedGoodLotMovement.movement_id).in_(
                                later_movement_ids
                            )
                        )
                    ).all()
                )
                if later_movement_ids != lot_linked_movement_ids:
                    raise BatchHasDownstreamActivity()
        for line in output_lines_with_stock:
            lot = lots_by_output_line[line.id]
            lot_entry = movements_by_lot[lot.id][0]
            if (
                lot.origin != FinishedGoodLotOrigin.PRODUCTION
                or lot.batch_id != batch.id
                or lot.output_line_id != line.id
                or lot.inventory_item_id != line.inventory_item_id
                or lot.produced_quantity != line.actual_good_quantity
                or lot_entry.movement_id != line.movement_id
            ):
                raise BatchNotReversible()

        input_reversals = post_movements(
            session,
            lines=[
                MovementLine(
                    item_id=movement.item_id,
                    quantity=-movement.quantity,
                    unit_cost=movement.unit_cost,
                    preserve_cost_uncertainty=movement.cost_uncertain,
                )
                for movement in ordered_input_movements
            ],
            movement_type=MovementType.REVERSAL,
            source_type="production_batch_reversal",
            source_id=batch.id,
            actor=actor,
            require_active=False,
        )
        output_reversals = post_movements(
            session,
            lines=[
                MovementLine(
                    item_id=movement.item_id,
                    quantity=-movement.quantity,
                    remove_at_cost=movement.unit_cost,
                    preserve_cost_uncertainty=movement.cost_uncertain,
                )
                for movement in ordered_output_movements
            ],
            movement_type=MovementType.REVERSAL,
            source_type="production_batch_reversal",
            source_id=batch.id,
            actor=actor,
            require_active=False,
        )
        for line, movement in zip(
            output_lines_with_stock, output_reversals, strict=True
        ):
            lot = lots_by_output_line[line.id]
            reversal_quantity = -movement.quantity
            lot.quantity_on_hand = quantity(
                lot.quantity_on_hand + reversal_quantity
            )
            lot.updated_at = movement.occurred_at
            session.add(lot)
            session.add(
                FinishedGoodLotMovement(
                    lot_id=lot.id,
                    movement_id=movement.id,
                    quantity=reversal_quantity,
                    created_at=movement.occurred_at,
                )
            )
            audit.record(
                session,
                actor=actor,
                entity_type="finished_good_lot",
                entity_id=lot.id,
                action="production_output_reversed",
                changes={
                    "quantity": reversal_quantity,
                    "batch_id": batch.id,
                    "movement_id": movement.id,
                },
            )

        reversed_at = get_datetime_utc()
        batch.status = ProductionBatchStatus.REVERSED
        batch.reversed_at = reversed_at
        batch.reversed_by_id = actor.id
        batch.reversal_reason = data.reason.strip()
        batch.updated_at = reversed_at
        session.add(batch)
        session.flush()
        audit.record(
            session,
            actor=actor,
            entity_type="production_batch",
            entity_id=batch.id,
            action="reversed",
            changes={
                "status": {
                    "old": ProductionBatchStatus.COMPLETED.value,
                    "new": batch.status.value,
                },
                "reason": batch.reversal_reason,
                "input_reversal_movement_ids": [
                    movement.id for movement in input_reversals
                ],
                "output_reversal_movement_ids": [
                    movement.id for movement in output_reversals
                ],
            },
        )
        result = _batch_public(session, batch)
        return 200, result.model_dump(mode="json")

    return idempotency.execute(
        session,
        scope="production.batch.reverse",
        key=idempotency_key,
        payload={"batch_id": str(batch_id), **data.model_dump(mode="json")},
        operation=operation,
    )
