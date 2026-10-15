import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select as sa_select
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, or_, select

from app.core.errors import violated_constraint
from app.core.money import quantity as round_quantity
from app.models import User, get_datetime_utc
from app.modules.audit import service as audit
from app.modules.idempotency import service as idempotency
from app.modules.idempotency.service import StoredResponse
from app.modules.inventory.errors import (
    AdjustmentAlreadyReversed,
    AdjustmentNotFound,
    BarcodeTaken,
    InvalidUnitConversion,
    InventoryCategoryNotFound,
    InventoryItemNotFound,
    ItemHasMovements,
    ItemInactive,
    NegativeStockNotAllowed,
    SkuTaken,
)
from app.modules.inventory.models import (
    ITEM_BARCODE_INDEX,
    ITEM_SKU_INDEX,
    ITEM_SKU_PREFIX,
    ITEM_SKU_SEQUENCE,
    AdjustmentReason,
    AdjustmentStatus,
    InventoryBalance,
    InventoryCategory,
    InventoryItem,
    InventoryMovement,
    ItemType,
    MovementType,
    StockAdjustment,
    StockAdjustmentLine,
)
from app.modules.inventory.schemas import (
    InventoryItemCreate,
    InventoryItemPublic,
    InventoryItemUpdate,
    InventoryMovementPublic,
    StockAdjustmentCreate,
    StockAdjustmentLinePublic,
    StockAdjustmentPublic,
    StockAdjustmentReverse,
    StockAdjustmentSummary,
)
from app.modules.inventory.valuation import apply_movement
from app.modules.settings.service import get_settings

ADJUSTMENT_SOURCE = "stock_adjustment"
ADJUSTMENT_POST_SCOPE = "inventory.adjustment.post"
ADJUSTMENT_REVERSE_SCOPE = "inventory.adjustment.reverse"

_ITEM_FIELDS = (
    "sku",
    "name",
    "description",
    "category_id",
    "item_type",
    "base_unit",
    "purchase_unit",
    "conversion_factor",
    "min_stock",
    "is_active",
    "barcode",
)


def _like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


# Posting


@dataclass(frozen=True)
class MovementLine:
    item_id: uuid.UUID
    quantity: Decimal
    """Signed change in base units."""
    unit_cost: Decimal | None = None
    """Cost per base unit for incoming stock; None uses the current average."""
    remove_at_cost: Decimal | None = None
    """Cost per base unit removed by a reversal; recomputes the average."""


def lock_balances(
    session: Session, item_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, InventoryBalance]:
    """Lock balance rows with SELECT ... FOR UPDATE in item-id order and return
    them freshly loaded. Raises if any item does not exist."""
    ids = sorted(set(item_ids))
    rows = session.exec(
        select(InventoryBalance)
        .where(col(InventoryBalance.item_id).in_(ids))
        .order_by(col(InventoryBalance.item_id))
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    if len(rows) != len(ids):
        raise InventoryItemNotFound()
    return {row.item_id: row for row in rows}


def _items_by_id(
    session: Session, item_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, InventoryItem]:
    ids = set(item_ids)
    items = session.exec(
        select(InventoryItem).where(col(InventoryItem.id).in_(ids))
    ).all()
    if len(items) != len(ids):
        raise InventoryItemNotFound()
    return {item.id: item for item in items}


def _assert_active(items: Iterable[InventoryItem]) -> None:
    for item in items:
        if not item.is_active:
            raise ItemInactive(f"Inventory item {item.sku} is inactive")


def post_movements(
    session: Session,
    *,
    lines: Sequence[MovementLine],
    movement_type: MovementType,
    source_type: str,
    source_id: uuid.UUID,
    actor: User | None,
    require_active: bool = True,
    allow_negative: bool | None = None,
) -> list[InventoryMovement]:
    """Append movements and update balances in the caller's transaction.

    The only writer of stock. Locks balances in sorted item order, values each
    line with weighted-average rules, and enforces the negative-stock policy on
    decreases (from business settings unless `allow_negative` is given).
    Flushes but never commits; returns movements in the order of `lines`.
    """
    if not lines:
        return []
    balances = lock_balances(session, (line.item_id for line in lines))
    items = _items_by_id(session, balances)
    if require_active:
        _assert_active(items.values())
    if allow_negative is None:
        allow_negative = get_settings(session).allow_negative_stock

    now = get_datetime_utc()
    movements: list[InventoryMovement] = []
    for line in lines:
        balance = balances[line.item_id]
        change = round_quantity(line.quantity)
        effect = apply_movement(
            quantity_before=balance.quantity,
            avg_cost_before=balance.avg_unit_cost,
            change=change,
            incoming_cost=line.unit_cost,
            remove_at_cost=line.remove_at_cost,
        )
        if change < 0 and effect.quantity_after < 0 and not allow_negative:
            item = items[line.item_id]
            raise NegativeStockNotAllowed(
                f"{item.sku} would drop to {effect.quantity_after} {item.base_unit.value}; "
                "negative stock is not allowed"
            )
        movement = InventoryMovement(
            item_id=line.item_id,
            movement_type=movement_type,
            quantity=change,
            unit_cost=effect.unit_cost,
            value=effect.value,
            quantity_after=effect.quantity_after,
            cost_uncertain=effect.cost_uncertain,
            source_type=source_type,
            source_id=source_id,
            actor_id=actor.id if actor else None,
            occurred_at=now,
        )
        balance.quantity = effect.quantity_after
        balance.avg_unit_cost = effect.avg_cost_after
        balance.value = effect.value_after
        balance.updated_at = now
        session.add(movement)
        session.add(balance)
        movements.append(movement)
    session.flush()
    return movements


# Categories


def list_categories(session: Session) -> list[InventoryCategory]:
    return list(
        session.exec(
            select(InventoryCategory)
            .where(col(InventoryCategory.is_active).is_(True))
            .order_by(col(InventoryCategory.sort_order), col(InventoryCategory.name))
        ).all()
    )


def _assert_category(session: Session, category_id: uuid.UUID) -> None:
    category = session.get(InventoryCategory, category_id)
    if category is None or not category.is_active:
        raise InventoryCategoryNotFound()


# Items


def to_public(item: InventoryItem, balance: InventoryBalance) -> InventoryItemPublic:
    return InventoryItemPublic.model_validate(
        {
            **item.model_dump(),
            "quantity": balance.quantity,
            "avg_unit_cost": balance.avg_unit_cost,
            "value": balance.value,
            "is_low_stock": item.min_stock > 0 and balance.quantity <= item.min_stock,
            "is_negative_stock": balance.quantity < 0,
        }
    )


def get_item(session: Session, item_id: uuid.UUID) -> InventoryItem:
    item = session.get(InventoryItem, item_id)
    if item is None:
        raise InventoryItemNotFound()
    return item


def get_item_public(session: Session, item_id: uuid.UUID) -> InventoryItemPublic:
    item = get_item(session, item_id)
    balance = session.get(InventoryBalance, item_id, populate_existing=True)
    assert balance is not None
    return to_public(item, balance)


def next_sku(session: Session) -> str:
    """Reserve the next `SP-NNNNN` SKU; numbers are never reused."""
    number = (
        session.connection()
        .execute(sa_select(ITEM_SKU_SEQUENCE.next_value()))
        .scalar_one()
    )
    return f"{ITEM_SKU_PREFIX}{number:05d}"


def _assert_barcode_free(
    session: Session, barcode: str | None, *, exclude_id: uuid.UUID | None = None
) -> None:
    if barcode is None:
        return
    query = select(InventoryItem.id).where(InventoryItem.barcode == barcode)
    if exclude_id is not None:
        query = query.where(InventoryItem.id != exclude_id)
    if session.exec(query).first() is not None:
        raise BarcodeTaken()


def _flush_or_conflict(session: Session) -> None:
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        constraint = violated_constraint(exc)
        if constraint == ITEM_SKU_INDEX:
            raise SkuTaken() from exc
        if constraint == ITEM_BARCODE_INDEX:
            raise BarcodeTaken() from exc
        raise


def create_item(
    session: Session, *, data: InventoryItemCreate, actor: User
) -> InventoryItemPublic:
    _assert_barcode_free(session, data.barcode)
    _assert_category(session, data.category_id)
    item = InventoryItem.model_validate(data, update={"sku": next_sku(session)})
    balance = InventoryBalance(item_id=item.id)
    session.add(item)
    _flush_or_conflict(session)
    session.add(balance)
    session.flush()
    audit.record(
        session,
        actor=actor,
        entity_type="inventory_item",
        entity_id=item.id,
        action="created",
        changes={f: {"old": None, "new": getattr(item, f)} for f in _ITEM_FIELDS},
    )
    session.commit()
    return get_item_public(session, item.id)


def update_item(
    session: Session, *, item_id: uuid.UUID, data: InventoryItemUpdate, actor: User
) -> InventoryItemPublic:
    item = get_item(session, item_id)
    old = item.model_dump()
    updates = data.model_dump(exclude_unset=True)
    nullable = {"description", "barcode"}
    updates = {k: v for k, v in updates.items() if v is not None or k in nullable}
    new = {**old, **updates}
    if new["purchase_unit"] == new["base_unit"] and new["conversion_factor"] != 1:
        raise InvalidUnitConversion()
    changes = audit.diff(old, new, _ITEM_FIELDS)
    if changes:
        _assert_barcode_free(session, updates.get("barcode"), exclude_id=item.id)
        if "category_id" in changes:
            _assert_category(session, updates["category_id"])
        item.sqlmodel_update(updates)
        item.updated_at = get_datetime_utc()
        session.add(item)
        _flush_or_conflict(session)
        audit.record(
            session,
            actor=actor,
            entity_type="inventory_item",
            entity_id=item.id,
            action="updated",
            changes=changes,
        )
        session.commit()
    return get_item_public(session, item.id)


def delete_item(session: Session, *, item_id: uuid.UUID, actor: User) -> None:
    item = get_item(session, item_id)
    has_movements = session.exec(
        select(InventoryMovement.id)
        .where(InventoryMovement.item_id == item_id)
        .limit(1)
    ).first()
    if has_movements is not None:
        raise ItemHasMovements()
    snapshot = {f: getattr(item, f) for f in _ITEM_FIELDS}
    balance = session.get(InventoryBalance, item_id)
    if balance is not None:
        session.delete(balance)
    session.delete(item)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ItemHasMovements() from exc
    audit.record(
        session,
        actor=actor,
        entity_type="inventory_item",
        entity_id=item_id,
        action="deleted",
        changes={f: {"old": v, "new": None} for f, v in snapshot.items()},
    )
    session.commit()


def search_items(
    session: Session,
    *,
    q: str | None = None,
    category_id: uuid.UUID | None = None,
    item_type: ItemType | None = None,
    is_active: bool | None = None,
    low_stock: bool = False,
    negative_stock: bool = False,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[InventoryItemPublic], int]:
    conditions: list[Any] = []
    if q and q.strip():
        pattern = _like(q.strip())
        conditions.append(
            or_(
                col(InventoryItem.sku).ilike(pattern, escape="\\"),
                col(InventoryItem.name).ilike(pattern, escape="\\"),
                col(InventoryItem.barcode).ilike(pattern, escape="\\"),
            )
        )
    if category_id is not None:
        conditions.append(col(InventoryItem.category_id) == category_id)
    if item_type is not None:
        conditions.append(col(InventoryItem.item_type) == item_type)
    if is_active is not None:
        conditions.append(col(InventoryItem.is_active).is_(is_active))
    if low_stock:
        conditions.append(col(InventoryItem.is_active).is_(True))
        conditions.append(col(InventoryItem.min_stock) > 0)
        conditions.append(
            col(InventoryBalance.quantity) <= col(InventoryItem.min_stock)
        )
    if negative_stock:
        conditions.append(col(InventoryBalance.quantity) < 0)

    base = select(InventoryItem, InventoryBalance).join(
        InventoryBalance, col(InventoryBalance.item_id) == col(InventoryItem.id)
    )
    count = session.exec(
        select(func.count())
        .select_from(InventoryItem)
        .join(InventoryBalance, col(InventoryBalance.item_id) == col(InventoryItem.id))
        .where(*conditions)
    ).one()
    rows = session.exec(
        base.where(*conditions)
        .order_by(col(InventoryItem.name), col(InventoryItem.sku))
        .offset(skip)
        .limit(limit)
    ).all()
    return [to_public(item, balance) for item, balance in rows], count


def list_movements(
    session: Session,
    *,
    item_id: uuid.UUID,
    movement_type: MovementType | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[InventoryMovementPublic], int]:
    """Newest first; `quantity_after` is the running balance after each movement."""
    get_item(session, item_id)
    conditions: list[Any] = [col(InventoryMovement.item_id) == item_id]
    if movement_type is not None:
        conditions.append(col(InventoryMovement.movement_type) == movement_type)
    if occurred_from is not None:
        conditions.append(col(InventoryMovement.occurred_at) >= occurred_from)
    if occurred_to is not None:
        conditions.append(col(InventoryMovement.occurred_at) < occurred_to)
    count = session.exec(
        select(func.count()).select_from(InventoryMovement).where(*conditions)
    ).one()
    rows = session.exec(
        select(InventoryMovement, User.email, User.full_name)
        .outerjoin(User, col(User.id) == col(InventoryMovement.actor_id))
        .where(*conditions)
        .order_by(col(InventoryMovement.seq).desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return [
        InventoryMovementPublic.model_validate(
            {**movement.model_dump(), "actor_email": email, "actor_name": name}
        )
        for movement, email, name in rows
    ], count


# Adjustments


def _adjustment_public(
    session: Session, adjustment: StockAdjustment
) -> StockAdjustmentPublic:
    rows = session.exec(
        select(StockAdjustmentLine, InventoryItem)
        .join(InventoryItem, col(InventoryItem.id) == col(StockAdjustmentLine.item_id))
        .where(StockAdjustmentLine.adjustment_id == adjustment.id)
        .order_by(col(StockAdjustmentLine.line_no))
    ).all()
    poster = session.get(User, adjustment.posted_by_id)
    return StockAdjustmentPublic.model_validate(
        {
            **adjustment.model_dump(),
            "posted_by_email": poster.email if poster else None,
            "posted_by_name": poster.full_name if poster else None,
            "lines": [
                StockAdjustmentLinePublic.model_validate(
                    {
                        **line.model_dump(),
                        "item_sku": item.sku,
                        "item_name": item.name,
                        "base_unit": item.base_unit,
                    }
                )
                for line, item in rows
            ],
        }
    )


def get_adjustment(session: Session, adjustment_id: uuid.UUID) -> StockAdjustmentPublic:
    adjustment = session.get(StockAdjustment, adjustment_id)
    if adjustment is None:
        raise AdjustmentNotFound()
    return _adjustment_public(session, adjustment)


def list_adjustments(
    session: Session,
    *,
    status: AdjustmentStatus | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[StockAdjustmentSummary], int]:
    conditions: list[Any] = []
    if status is not None:
        conditions.append(col(StockAdjustment.status) == status)
    count = session.exec(
        select(func.count()).select_from(StockAdjustment).where(*conditions)
    ).one()
    line_count = (
        select(func.count())
        .where(StockAdjustmentLine.adjustment_id == StockAdjustment.id)
        .correlate(StockAdjustment)
        .scalar_subquery()
    )
    rows = session.exec(
        select(StockAdjustment, User.email, User.full_name, line_count)
        .outerjoin(User, col(User.id) == col(StockAdjustment.posted_by_id))
        .where(*conditions)
        .order_by(col(StockAdjustment.number).desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return [
        StockAdjustmentSummary.model_validate(
            {
                **adjustment.model_dump(),
                "posted_by_email": email,
                "posted_by_name": name,
                "line_count": lines,
            }
        )
        for adjustment, email, name, lines in rows
    ], count


def post_adjustment(
    session: Session,
    *,
    data: StockAdjustmentCreate,
    actor: User,
    idempotency_key: str,
) -> StoredResponse:
    """Post all lines or none; repeating `idempotency_key` returns the original."""

    def operation() -> tuple[int, Any]:
        item_ids = [line.item_id for line in data.lines]
        balances = lock_balances(session, item_ids)
        items = _items_by_id(session, item_ids)
        _assert_active(items.values())

        adjustment = StockAdjustment(note=data.note, posted_by_id=actor.id)
        session.add(adjustment)
        session.flush()

        planned: list[tuple[int, Any, Decimal, Decimal]] = []
        movement_lines: list[MovementLine] = []
        for line_no, line in enumerate(data.lines, start=1):
            previous = balances[line.item_id].quantity
            if line.reason == AdjustmentReason.PHYSICAL_COUNT:
                assert line.counted_quantity is not None
                change = round_quantity(line.counted_quantity - previous)
            else:
                assert line.quantity_change is not None
                change = round_quantity(line.quantity_change)
            planned.append((line_no, line, previous, change))
            if change != 0:
                movement_lines.append(
                    MovementLine(
                        item_id=line.item_id,
                        quantity=change,
                        unit_cost=line.unit_cost if change > 0 else None,
                    )
                )

        movements = iter(
            post_movements(
                session,
                lines=movement_lines,
                movement_type=MovementType.ADJUSTMENT,
                source_type=ADJUSTMENT_SOURCE,
                source_id=adjustment.id,
                actor=actor,
            )
        )
        for line_no, line, previous, change in planned:
            movement = next(movements) if change != 0 else None
            session.add(
                StockAdjustmentLine(
                    adjustment_id=adjustment.id,
                    line_no=line_no,
                    item_id=line.item_id,
                    reason=line.reason,
                    counted_quantity=line.counted_quantity,
                    previous_quantity=previous,
                    quantity_change=change,
                    resulting_quantity=round_quantity(previous + change),
                    unit_cost=(
                        movement.unit_cost
                        if movement
                        else balances[line.item_id].avg_unit_cost
                    ),
                    movement_id=movement.id if movement else None,
                )
            )
        session.flush()
        audit.record(
            session,
            actor=actor,
            entity_type=ADJUSTMENT_SOURCE,
            entity_id=adjustment.id,
            action="posted",
            changes={
                "lines": [
                    {
                        "item_id": line.item_id,
                        "reason": line.reason,
                        "previous": previous,
                        "change": change,
                        "result": previous + change,
                    }
                    for _, line, previous, change in planned
                ]
            },
        )
        return 201, _adjustment_public(session, adjustment)

    return idempotency.execute(
        session,
        scope=ADJUSTMENT_POST_SCOPE,
        key=idempotency_key,
        payload=data.model_dump(mode="json"),
        operation=operation,
    )


def reverse_adjustment(
    session: Session,
    *,
    adjustment_id: uuid.UUID,
    data: StockAdjustmentReverse,
    actor: User,
    idempotency_key: str,
) -> StoredResponse:
    """Post equal and opposite movements and mark the adjustment reversed."""

    def operation() -> tuple[int, Any]:
        adjustment = session.exec(
            select(StockAdjustment)
            .where(StockAdjustment.id == adjustment_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).first()
        if adjustment is None:
            raise AdjustmentNotFound()
        if adjustment.status != AdjustmentStatus.POSTED:
            raise AdjustmentAlreadyReversed()

        originals = session.exec(
            select(InventoryMovement)
            .join(
                StockAdjustmentLine,
                col(StockAdjustmentLine.movement_id) == col(InventoryMovement.id),
            )
            .where(StockAdjustmentLine.adjustment_id == adjustment.id)
            .order_by(col(StockAdjustmentLine.line_no))
        ).all()
        post_movements(
            session,
            lines=[
                MovementLine(
                    item_id=m.item_id,
                    quantity=-m.quantity,
                    unit_cost=m.unit_cost if m.quantity < 0 else None,
                )
                for m in originals
            ],
            movement_type=MovementType.REVERSAL,
            source_type=ADJUSTMENT_SOURCE,
            source_id=adjustment.id,
            actor=actor,
            require_active=False,
        )
        adjustment.status = AdjustmentStatus.REVERSED
        adjustment.reversed_at = get_datetime_utc()
        adjustment.reversed_by_id = actor.id
        adjustment.reversal_note = data.note
        session.add(adjustment)
        session.flush()
        audit.record(
            session,
            actor=actor,
            entity_type=ADJUSTMENT_SOURCE,
            entity_id=adjustment.id,
            action="reversed",
            changes={"status": {"old": "posted", "new": "reversed"}, "note": data.note},
        )
        return 200, _adjustment_public(session, adjustment)

    return idempotency.execute(
        session,
        scope=ADJUSTMENT_REVERSE_SCOPE,
        key=idempotency_key,
        payload={"adjustment_id": str(adjustment_id), **data.model_dump(mode="json")},
        operation=operation,
    )
