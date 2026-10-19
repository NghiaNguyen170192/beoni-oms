import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from app.core.errors import violated_constraint
from app.core.money import money, quantity, unit_cost
from app.models import User, get_datetime_utc
from app.modules.audit import service as audit
from app.modules.catalog.errors import MenuItemNotFound
from app.modules.catalog.models import MenuItem, ProductType
from app.modules.idempotency import service as idempotency
from app.modules.idempotency.service import StoredResponse
from app.modules.inventory.errors import InventoryItemNotFound, ItemInactive
from app.modules.inventory.models import (
    InventoryBalance,
    InventoryItem,
    InventoryMovement,
    InventoryRole,
    MovementType,
)
from app.modules.inventory.service import MovementLine, lock_balances, post_movements
from app.modules.ordering.errors import OrderLineNotFound
from app.modules.ordering.models import Order, OrderLine
from app.modules.ordering.states import OrderStatus
from app.modules.production.models import (
    FinishedGoodLot,
    FinishedGoodLotAllocation,
    FinishedGoodLotMovement,
    ProductionBatch,
)
from app.modules.recipes.consumption import (
    NON_STOCK,
    Allocation,
    Component,
    ConsumptionLine,
    aggregate_requirements,
    allocate_movement,
)
from app.modules.recipes.errors import (
    DuplicateRecipeLine,
    InsufficientStock,
    InvalidRecipeInput,
    InvalidRecipeOutput,
    MissingConsumption,
    PreparedReturnRejected,
    RecipeNotAllowed,
    RecipeNotFound,
    RecipeOutputMappingConflict,
    ReturnExceedsSold,
    ReturnNotAllowed,
    Shortage,
    VersionConflict,
)
from app.modules.recipes.models import (
    MovementAllocation,
    Recipe,
    RecipeKind,
    RecipeLine,
    RecipeOutputLine,
    StockReturn,
    StockReturnLine,
)
from app.modules.recipes.schemas import (
    CostPreviewLinePublic,
    CostPreviewPublic,
    RecipeLinePublic,
    RecipeOutputLinePublic,
    RecipePublic,
    RecipeVersionCreate,
    StockReturnCreate,
    StockReturnLinePublic,
    StockReturnPublic,
)
from app.modules.settings.service import get_settings

ORDER_SOURCE = "order"
RETURN_SCOPE = "stock.return"
RETURNABLE = frozenset(
    {
        OrderStatus.COMPLETED,
        OrderStatus.PARTIALLY_REFUNDED,
        OrderStatus.REFUNDED,
    }
)
_KIND_FOR = {
    ProductType.PREPARED: RecipeKind.RECIPE,
    ProductType.DIRECT_SALE: RecipeKind.STOCK_LINK,
}


def _kind_for(product_type: ProductType) -> RecipeKind:
    kind = _KIND_FOR.get(product_type)
    if kind is None:
        raise RecipeNotAllowed(
            "Only prepared items have recipes and only direct-sale items have a stock link"
        )
    return kind


def _recipe_lines(session: Session, recipe_id: uuid.UUID) -> list[RecipeLine]:
    return list(
        session.exec(
            select(RecipeLine)
            .where(RecipeLine.recipe_id == recipe_id)
            .order_by(col(RecipeLine.inventory_item_id))
        ).all()
    )


def _recipe_outputs(
    session: Session, recipe_id: uuid.UUID
) -> list[RecipeOutputLine]:
    return list(
        session.exec(
            select(RecipeOutputLine)
            .where(RecipeOutputLine.recipe_id == recipe_id)
            .order_by(col(RecipeOutputLine.menu_item_id))
        ).all()
    )


def _inventory_map(
    session: Session, item_ids: set[uuid.UUID]
) -> dict[uuid.UUID, InventoryItem]:
    if not item_ids:
        return {}
    rows = session.exec(
        select(InventoryItem).where(col(InventoryItem.id).in_(item_ids))
    ).all()
    if len(rows) != len(item_ids):
        raise InventoryItemNotFound()
    return {row.id: row for row in rows}


def _to_public(session: Session, recipe: Recipe) -> RecipePublic:
    menu_item = session.get(MenuItem, recipe.menu_item_id)
    if menu_item is None:
        raise MenuItemNotFound()
    rows = _recipe_lines(session, recipe.id)
    items = _inventory_map(session, {row.inventory_item_id for row in rows})
    output_rows = _recipe_outputs(session, recipe.id)
    output_items = _inventory_map(
        session, {row.inventory_item_id for row in output_rows}
    )
    output_menu_items: dict[uuid.UUID, MenuItem] = {}
    for row in output_rows:
        output_menu_item = session.get(MenuItem, row.menu_item_id)
        if output_menu_item is None:
            raise MenuItemNotFound()
        output_menu_items[row.menu_item_id] = output_menu_item
    return RecipePublic(
        id=recipe.id,
        menu_item_id=recipe.menu_item_id,
        menu_item_name=menu_item.name,
        menu_item_code=menu_item.code,
        product_type=menu_item.product_type,
        version=recipe.version,
        kind=recipe.kind,
        effective_from=recipe.effective_from,
        created_at=recipe.created_at,
        lines=[
            RecipeLinePublic(
                id=row.id,
                inventory_item_id=row.inventory_item_id,
                item_sku=items[row.inventory_item_id].sku,
                item_name=items[row.inventory_item_id].name,
                base_unit=items[row.inventory_item_id].base_unit,
                quantity=row.quantity,
            )
            for row in rows
        ],
        outputs=[
            RecipeOutputLinePublic(
                id=row.id,
                menu_item_id=row.menu_item_id,
                menu_item_name=output_menu_items[row.menu_item_id].name,
                menu_item_code=output_menu_items[row.menu_item_id].code,
                inventory_item_id=row.inventory_item_id,
                item_sku=output_items[row.inventory_item_id].sku,
                item_name=output_items[row.inventory_item_id].name,
                base_unit=output_items[row.inventory_item_id].base_unit,
                quantity=row.quantity,
            )
            for row in output_rows
        ],
    )


def _line_snapshot(rows: list[RecipeLine]) -> list[dict[str, Any]]:
    return [
        {"inventory_item_id": row.inventory_item_id, "quantity": row.quantity}
        for row in rows
    ]


def _output_snapshot(rows: list[RecipeOutputLine]) -> list[dict[str, Any]]:
    return [
        {
            "menu_item_id": row.menu_item_id,
            "inventory_item_id": row.inventory_item_id,
            "quantity": row.quantity,
        }
        for row in rows
    ]


def _flush_version(session: Session) -> None:
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        constraint = violated_constraint(exc)
        if constraint == "uq_recipe_lines_item":
            raise DuplicateRecipeLine() from exc
        if constraint == "uq_recipe_output_lines_menu_item":
            raise InvalidRecipeOutput() from exc
        if constraint in {"uq_recipes_item_version", "uq_recipes_item_effective"}:
            raise VersionConflict() from exc
        raise


def create_version(
    session: Session, *, data: RecipeVersionCreate, actor: User
) -> RecipePublic:
    """Save a new recipe or stock-link version. Earlier versions stay as they were."""
    menu_item_ids = {data.menu_item_id} | {
        output.menu_item_id for output in data.outputs
    }
    menu_items = session.exec(
        select(MenuItem)
        .where(col(MenuItem.id).in_(menu_item_ids))
        .order_by(col(MenuItem.id))
        .with_for_update()
    ).all()
    menu_item_map = {item.id: item for item in menu_items}
    if len(menu_item_map) != len(menu_item_ids):
        raise MenuItemNotFound()
    menu_item = menu_item_map[data.menu_item_id]
    if data.outputs and menu_item.product_type == ProductType.NON_STOCK:
        raise RecipeNotAllowed("Non-stock items cannot be production formula outputs")
    kind = RecipeKind.RECIPE if data.outputs else _kind_for(menu_item.product_type)
    if kind == RecipeKind.STOCK_LINK and len(data.lines) != 1:
        raise RecipeNotAllowed(
            "A direct-sale stock link has exactly one inventory item"
        )
    if data.outputs and any(
        output_menu_item.product_type == ProductType.NON_STOCK
        or not output_menu_item.is_active
        for output_menu_item in menu_items
    ):
        raise InvalidRecipeOutput()

    item_ids = {line.inventory_item_id for line in data.lines}
    output_item_ids = {line.inventory_item_id for line in data.outputs}
    items = _inventory_map(session, item_ids)
    output_items = _inventory_map(session, output_item_ids)
    for item in items.values():
        if not item.is_active:
            raise ItemInactive(f"Inventory item {item.sku} is inactive")
        if data.outputs and item.role != InventoryRole.RAW_MATERIAL:
            raise InvalidRecipeInput()
    for item in output_items.values():
        if (
            not item.is_active
            or item.role != InventoryRole.FINISHED_GOOD
        ):
            raise InvalidRecipeOutput()

    if data.outputs:
        existing_mappings = session.exec(
            select(RecipeOutputLine)
            .where(col(RecipeOutputLine.menu_item_id).in_(menu_item_ids))
            .order_by(col(RecipeOutputLine.menu_item_id))
        ).all()
        mappings_by_menu: dict[uuid.UUID, set[uuid.UUID]] = {}
        for row in existing_mappings:
            mappings_by_menu.setdefault(row.menu_item_id, set()).add(
                row.inventory_item_id
            )
        from app.modules.production.models import ProductionBatchOutputLine

        batch_mappings = session.exec(
            select(
                ProductionBatchOutputLine.menu_item_id,
                ProductionBatchOutputLine.inventory_item_id,
            ).where(col(ProductionBatchOutputLine.menu_item_id).in_(menu_item_ids))
        ).all()
        for output_menu_item_id, inventory_item_id in batch_mappings:
            mappings_by_menu.setdefault(output_menu_item_id, set()).add(
                inventory_item_id
            )
        if any(
            output.menu_item_id in mappings_by_menu
            and mappings_by_menu[output.menu_item_id] != {output.inventory_item_id}
            for output in data.outputs
        ):
            raise RecipeOutputMappingConflict()

    current = session.exec(
        select(func.coalesce(func.max(Recipe.version), 0)).where(
            Recipe.menu_item_id == menu_item.id
        )
    ).one()
    version = int(current) + 1
    previous = session.exec(
        select(Recipe).where(
            Recipe.menu_item_id == menu_item.id, Recipe.version == version - 1
        )
    ).first()
    old_lines = _recipe_lines(session, previous.id) if previous is not None else []
    old_outputs = (
        _recipe_outputs(session, previous.id) if previous is not None else []
    )

    recipe = Recipe(
        menu_item_id=menu_item.id,
        version=version,
        kind=kind,
        effective_from=data.effective_from,
        created_by_id=actor.id,
    )
    session.add(recipe)
    _flush_version(session)
    new_lines = [
        RecipeLine(
            recipe_id=recipe.id,
            inventory_item_id=line.inventory_item_id,
            quantity=quantity(line.quantity),
        )
        for line in data.lines
    ]
    session.add_all(new_lines)
    _flush_version(session)
    new_outputs = [
        RecipeOutputLine(
            recipe_id=recipe.id,
            menu_item_id=line.menu_item_id,
            inventory_item_id=line.inventory_item_id,
            quantity=quantity(line.quantity),
        )
        for line in data.outputs
    ]
    session.add_all(new_outputs)
    _flush_version(session)
    audit.record(
        session,
        actor=actor,
        entity_type="recipe",
        entity_id=recipe.id,
        action="version_created",
        changes={
            "menu_item_id": menu_item.id,
            "version": version,
            "kind": kind.value,
            "effective_from": data.effective_from,
            "lines": {"old": _line_snapshot(old_lines), "new": _line_snapshot(new_lines)},
            "outputs": {
                "old": _output_snapshot(old_outputs),
                "new": _output_snapshot(new_outputs),
            },
        },
    )
    session.commit()
    return _to_public(session, recipe)


def list_versions(
    session: Session, *, menu_item_id: uuid.UUID
) -> tuple[list[RecipePublic], int]:
    if session.get(MenuItem, menu_item_id) is None:
        raise MenuItemNotFound()
    rows = session.exec(
        select(Recipe)
        .where(Recipe.menu_item_id == menu_item_id)
        .order_by(col(Recipe.version).desc())
    ).all()
    return [_to_public(session, row) for row in rows], len(rows)


def get_version(session: Session, recipe_id: uuid.UUID) -> RecipePublic:
    recipe = session.get(Recipe, recipe_id)
    if recipe is None:
        raise RecipeNotFound()
    return _to_public(session, recipe)


def applicable_version(
    session: Session,
    *,
    menu_item_id: uuid.UUID,
    kind: RecipeKind,
    at: datetime,
) -> Recipe | None:
    """The version in force at `at`: latest effective_from that is not after `at`."""
    return session.exec(
        select(Recipe)
        .where(
            Recipe.menu_item_id == menu_item_id,
            Recipe.kind == kind,
            Recipe.effective_from <= at,
        )
        .order_by(col(Recipe.effective_from).desc(), col(Recipe.version).desc())
        .limit(1)
    ).first()


def cost_preview(session: Session, recipe_id: uuid.UUID) -> CostPreviewPublic:
    """Estimated cost per serving from current average costs. Unknown lines are flagged."""
    recipe = session.get(Recipe, recipe_id)
    if recipe is None:
        raise RecipeNotFound()
    rows = _recipe_lines(session, recipe.id)
    items = _inventory_map(session, {row.inventory_item_id for row in rows})
    balances = {
        item_id: session.get(InventoryBalance, item_id) for item_id in items
    }
    preview: list[CostPreviewLinePublic] = []
    total = Decimal("0")
    for row in rows:
        item = items[row.inventory_item_id]
        balance = balances[row.inventory_item_id]
        avg = balance.avg_unit_cost if balance is not None else Decimal("0")
        unknown = avg == 0
        line_cost = None if unknown else money(row.quantity * avg)
        if line_cost is not None:
            total += line_cost
        preview.append(
            CostPreviewLinePublic(
                inventory_item_id=item.id,
                item_sku=item.sku,
                item_name=item.name,
                base_unit=item.base_unit,
                quantity=row.quantity,
                avg_unit_cost=avg,
                line_cost=line_cost,
                cost_unknown=unknown,
            )
        )
    return CostPreviewPublic(
        recipe_id=recipe.id, estimated_cost=money(total), lines=preview
    )


def _applicable_map(
    session: Session, menu_item_ids: set[uuid.UUID], at: datetime
) -> dict[tuple[uuid.UUID, RecipeKind], Recipe]:
    """One query: the applicable version of each kind for each menu item."""
    if not menu_item_ids:
        return {}
    rows = session.exec(
        select(Recipe)
        .where(
            col(Recipe.menu_item_id).in_(menu_item_ids),
            Recipe.effective_from <= at,
        )
        .order_by(
            col(Recipe.menu_item_id),
            col(Recipe.kind),
            col(Recipe.effective_from).desc(),
            col(Recipe.version).desc(),
        )
    ).all()
    chosen: dict[tuple[uuid.UUID, RecipeKind], Recipe] = {}
    for recipe in rows:
        chosen.setdefault((recipe.menu_item_id, recipe.kind), recipe)
    return chosen


def _components(
    session: Session, recipe_ids: set[uuid.UUID]
) -> dict[uuid.UUID, tuple[Component, ...]]:
    grouped: dict[uuid.UUID, list[Component]] = {recipe_id: [] for recipe_id in recipe_ids}
    if recipe_ids:
        rows = session.exec(
            select(RecipeLine).where(col(RecipeLine.recipe_id).in_(recipe_ids))
        ).all()
        for row in rows:
            grouped[row.recipe_id].append(
                Component(row.inventory_item_id, row.quantity)
            )
    return {recipe_id: tuple(lines) for recipe_id, lines in grouped.items()}


def _stamp_lines(
    session: Session,
    lines: list[OrderLine],
    *,
    recipe_ids: dict[uuid.UUID, uuid.UUID | None],
    cogs: dict[uuid.UUID, Decimal],
    uncertain: set[uuid.UUID],
) -> None:
    for line in lines:
        line.recipe_version_id = recipe_ids[line.id]
        line.cogs_amount = money(cogs[line.id])
        line.cost_uncertain = line.id in uncertain
        session.add(line)
    session.flush()


def consume_stock(
    session: Session, order: Order, lines: list[OrderLine], actor: User
) -> None:
    """Deduct aggregated stock and capture line COGS. Does not commit.

    Raises `MissingConsumption` or `InsufficientStock` before any movement is written
    when the sale cannot be fulfilled. The caller holds the order lock and commits.
    """
    at = get_datetime_utc()
    stock_lines = [line for line in lines if line.product_type.value != NON_STOCK]
    chosen = _applicable_map(session, {line.menu_item_id for line in stock_lines}, at)

    missing: list[str] = []
    selected: dict[uuid.UUID, Recipe] = {}
    for line in stock_lines:
        kind = _kind_for(line.product_type)
        recipe = chosen.get((line.menu_item_id, kind))
        if recipe is None:
            missing.append(line.item_name)
        else:
            selected[line.id] = recipe
    if missing:
        raise MissingConsumption(list(dict.fromkeys(missing)))

    components = _components(session, {recipe.id for recipe in selected.values()})
    consumption = [
        ConsumptionLine(
            order_line_id=line.id,
            quantity=line.quantity,
            product_type=line.product_type.value,
            recipe_id=None if line.id not in selected else selected[line.id].id,
            components=() if line.id not in selected else components[selected[line.id].id],
        )
        for line in lines
    ]
    requirements = aggregate_requirements(consumption)
    cogs = {line.id: Decimal("0") for line in lines}
    uncertain: set[uuid.UUID] = set()
    recipe_ids: dict[uuid.UUID, uuid.UUID | None] = {
        usage.order_line_id: usage.recipe_id for usage in requirements.by_line
    }

    if requirements.by_item:
        balances = lock_balances(session, requirements.by_item)
        items = _inventory_map(session, set(requirements.by_item))
        allow_negative = get_settings(session).allow_negative_stock
        if not allow_negative:
            shortages = [
                Shortage(
                    item_id=item_id,
                    item=items[item_id].name,
                    sku=items[item_id].sku,
                    required=required,
                    available=balances[item_id].quantity,
                    unit=items[item_id].base_unit.value,
                )
                for item_id, required in sorted(requirements.by_item.items())
                if required > balances[item_id].quantity
            ]
            if shortages:
                raise InsufficientStock(shortages)

        parts_by_item: dict[uuid.UUID, dict[uuid.UUID, Decimal]] = {}
        for usage in requirements.by_line:
            for item_id, used in usage.quantities.items():
                parts_by_item.setdefault(item_id, {})[usage.order_line_id] = used

        movements = post_movements(
            session,
            lines=[
                MovementLine(item_id=item_id, quantity=-required)
                for item_id, required in sorted(requirements.by_item.items())
            ],
            movement_type=MovementType.SALE_CONSUMPTION,
            source_type=ORDER_SOURCE,
            source_id=order.id,
            actor=actor,
            require_active=False,
            allow_negative=allow_negative,
        )
        _write_allocations(
            session,
            movements,
            parts_by_item,
            cogs=cogs,
            uncertain=uncertain,
        )

    _stamp_lines(
        session, lines, recipe_ids=recipe_ids, cogs=cogs, uncertain=uncertain
    )


def _write_allocations(
    session: Session,
    movements: list[InventoryMovement],
    parts_by_item: dict[uuid.UUID, dict[uuid.UUID, Decimal]],
    *,
    cogs: dict[uuid.UUID, Decimal],
    uncertain: set[uuid.UUID],
) -> None:
    for movement in movements:
        shares: list[Allocation] = allocate_movement(
            movement_quantity=movement.quantity,
            movement_value=movement.value,
            parts=parts_by_item[movement.item_id],
        )
        for share in shares:
            session.add(
                MovementAllocation(
                    movement_id=movement.id,
                    order_line_id=share.order_line_id,
                    quantity=share.quantity,
                    value=share.value,
                )
            )
            cogs[share.order_line_id] += -share.value
            if movement.cost_uncertain:
                uncertain.add(share.order_line_id)
    session.flush()


def _returned_quantity(session: Session, order_line_id: uuid.UUID) -> Decimal:
    total = session.exec(
        select(func.coalesce(func.sum(StockReturnLine.quantity), 0)).where(
            StockReturnLine.order_line_id == order_line_id
        )
    ).one()
    return Decimal(total)


def _return_public(session: Session, document: StockReturn) -> StockReturnPublic:
    rows = session.exec(
        select(StockReturnLine, OrderLine, FinishedGoodLot, ProductionBatch)
        .join(OrderLine, col(OrderLine.id) == col(StockReturnLine.order_line_id))
        .outerjoin(
            FinishedGoodLot,
            col(FinishedGoodLot.id) == col(StockReturnLine.finished_good_lot_id),
        )
        .outerjoin(
            ProductionBatch,
            col(ProductionBatch.id) == col(FinishedGoodLot.batch_id),
        )
        .where(StockReturnLine.stock_return_id == document.id)
        .order_by(col(StockReturnLine.id))
    ).all()
    return StockReturnPublic(
        id=document.id,
        order_id=document.order_id,
        reason=document.reason,
        created_by_id=document.created_by_id,
        created_at=document.created_at,
        lines=[
            StockReturnLinePublic(
                id=row.id,
                order_line_id=row.order_line_id,
                item_name=line.item_name,
                quantity=row.quantity,
                sellable=row.sellable,
                unit_cost=row.unit_cost,
                movement_id=row.movement_id,
                finished_good_lot_id=row.finished_good_lot_id,
                finished_good_lot_allocation_id=row.finished_good_lot_allocation_id,
                lot_number=lot.lot_number if lot else None,
                batch_id=lot.batch_id if lot else None,
                batch_number=batch.number if batch else None,
                finished_at=lot.finished_at if lot else None,
            )
            for row, line, lot, batch in rows
        ],
    )


def list_returns(
    session: Session, *, order_id: uuid.UUID, actor: User
) -> tuple[list[StockReturnPublic], int]:
    from app.modules.ordering.service import _load

    _load(session, order_id, actor)
    rows = session.exec(
        select(StockReturn)
        .where(StockReturn.order_id == order_id)
        .order_by(col(StockReturn.created_at))
    ).all()
    data = [_return_public(session, row) for row in rows]
    return data, len(data)


def return_to_stock(
    session: Session,
    *,
    order_id: uuid.UUID,
    data: StockReturnCreate,
    actor: User,
    idempotency_key: str,
) -> StoredResponse:
    """Return sold stock to its source lot, once per idempotency key."""
    from app.modules.ordering.service import _lines, _load

    def operation() -> tuple[int, StockReturnPublic]:
        order = _load(session, order_id, actor, for_update=True)
        if order.status not in RETURNABLE:
            raise ReturnNotAllowed()
        order_lines = {line.id: line for line in _lines(session, order.id)}
        planned: list[
            tuple[
                Any,
                OrderLine,
                uuid.UUID,
                Decimal | None,
                FinishedGoodLot | None,
                FinishedGoodLotAllocation | None,
                Decimal,
            ]
        ] = []
        for incoming in data.lines:
            line = order_lines.get(incoming.order_line_id)
            if line is None:
                raise OrderLineNotFound()
            returning = quantity(incoming.quantity)
            if _returned_quantity(session, line.id) + returning > line.quantity:
                raise ReturnExceedsSold()
            lot_allocations = session.exec(
                select(FinishedGoodLotAllocation, FinishedGoodLot)
                .join(
                    FinishedGoodLotMovement,
                    col(FinishedGoodLotMovement.id)
                    == col(FinishedGoodLotAllocation.lot_movement_id),
                )
                .join(
                    FinishedGoodLot,
                    col(FinishedGoodLot.id) == col(FinishedGoodLotMovement.lot_id),
                )
                .where(FinishedGoodLotAllocation.order_line_id == line.id)
                .order_by(
                    col(FinishedGoodLotAllocation.created_at),
                    col(FinishedGoodLotAllocation.id),
                )
            ).all()
            if lot_allocations:
                allocation_ids = [row[0].id for row in lot_allocations]
                prior_returns = {
                    allocation_id: returned
                    for allocation_id, returned in session.exec(
                        select(
                            StockReturnLine.finished_good_lot_allocation_id,
                            func.sum(StockReturnLine.quantity),
                        )
                        .where(
                            col(
                                StockReturnLine.finished_good_lot_allocation_id
                            ).in_(allocation_ids)
                        )
                        .group_by(
                            col(StockReturnLine.finished_good_lot_allocation_id)
                        )
                    ).all()
                }
                unallocated_return = returning
                for allocation, lot in lot_allocations:
                    already_returned = Decimal(
                        prior_returns.get(allocation.id, Decimal("0"))
                    )
                    can_return = max(
                        Decimal("0"),
                        quantity(allocation.quantity - already_returned),
                    )
                    allocated_return = min(can_return, unallocated_return)
                    if allocated_return <= 0:
                        continue
                    planned.append(
                        (
                            incoming,
                            line,
                            lot.inventory_item_id,
                            None,
                            lot,
                            allocation,
                            allocated_return,
                        )
                    )
                    unallocated_return = quantity(
                        unallocated_return - allocated_return
                    )
                    if unallocated_return <= 0:
                        break
                if unallocated_return > 0:
                    raise ReturnExceedsSold()
                continue

            if line.product_type != ProductType.DIRECT_SALE:
                raise PreparedReturnRejected()
            if line.recipe_version_id is None:
                raise ReturnNotAllowed("This line has no recorded stock link")
            link_lines = _recipe_lines(session, line.recipe_version_id)
            if len(link_lines) != 1:
                raise ReturnNotAllowed("Stock link must reference one inventory item")
            per_unit = (
                unit_cost(line.cogs_amount / line.quantity)
                if line.cogs_amount is not None
                else Decimal("0")
            )
            planned.append(
                (
                    incoming,
                    line,
                    link_lines[0].inventory_item_id,
                    per_unit,
                    None,
                    None,
                    returning,
                )
            )

        sellable = [entry for entry in planned if entry[0].sellable]
        if sellable:
            lock_balances(session, {entry[2] for entry in sellable})
            lots_by_id = {
                lot.id: lot
                for lot in session.exec(
                    select(FinishedGoodLot)
                    .where(
                        col(FinishedGoodLot.id).in_(
                            {
                                entry[4].id
                                for entry in sellable
                                if entry[4] is not None
                            }
                        )
                    )
                    .with_for_update()
                    .execution_options(populate_existing=True)
                ).all()
            }
        else:
            lots_by_id = {}

        document = StockReturn(
            order_id=order.id, reason=data.reason, created_by_id=actor.id
        )
        session.add(document)
        session.flush()
        movements = post_movements(
            session,
            lines=[
                MovementLine(
                    item_id=entry[2],
                    quantity=entry[6],
                    unit_cost=entry[3],
                    preserve_cost_uncertainty=entry[4] is not None,
                )
                for entry in sellable
            ],
            movement_type=MovementType.RETURN,
            source_type=ORDER_SOURCE,
            source_id=order.id,
            actor=actor,
            require_active=False,
            allow_negative=True,
        )
        posted = iter(movements)
        for (
            incoming,
            line,
            _,
            per_unit,
            lot,
            allocation,
            return_quantity,
        ) in planned:
            movement = next(posted) if incoming.sellable else None
            if movement is not None and lot is not None:
                locked_lot = lots_by_id[lot.id]
                locked_lot.quantity_on_hand = quantity(
                    locked_lot.quantity_on_hand + return_quantity
                )
                locked_lot.updated_at = movement.occurred_at
                session.add(locked_lot)
                session.add(
                    FinishedGoodLotMovement(
                        lot_id=locked_lot.id,
                        movement_id=movement.id,
                        quantity=return_quantity,
                        created_at=movement.occurred_at,
                    )
                )
            session.add(
                StockReturnLine(
                    stock_return_id=document.id,
                    order_line_id=line.id,
                    quantity=return_quantity,
                    sellable=incoming.sellable,
                    unit_cost=per_unit,
                    movement_id=movement.id if movement else None,
                    finished_good_lot_id=lot.id if lot else None,
                    finished_good_lot_allocation_id=(
                        allocation.id if allocation else None
                    ),
                )
            )
        session.flush()
        audit.record(
            session,
            actor=actor,
            entity_type="stock_return",
            entity_id=document.id,
            action="returned",
            changes={
                "order_id": order.id,
                "reason": data.reason,
                "lines": [
                    {
                        "order_line_id": line.id,
                        "quantity": return_quantity,
                        "sellable": incoming.sellable,
                        "finished_good_lot_id": lot.id if lot else None,
                        "finished_good_lot_allocation_id": (
                            allocation.id if allocation else None
                        ),
                    }
                    for (
                        incoming,
                        line,
                        _,
                        _,
                        lot,
                        allocation,
                        return_quantity,
                    ) in planned
                ],
            },
        )
        return 201, _return_public(session, document)

    return idempotency.execute(
        session,
        scope=RETURN_SCOPE,
        key=idempotency_key,
        payload={"order_id": str(order_id), **data.model_dump(mode="json")},
        operation=operation,
    )
