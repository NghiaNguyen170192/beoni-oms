import uuid
from collections.abc import Callable
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import Session, col, func, select

from app.models import User, get_datetime_utc
from app.modules.audit import service as audit
from app.modules.catalog import service as catalog
from app.modules.catalog.models import MenuItem
from app.modules.catalog.service import like_pattern
from app.modules.idempotency import service as idempotency
from app.modules.idempotency.service import StoredResponse
from app.modules.identity.permissions import Permission, has_permission
from app.modules.ordering.errors import (
    EmptyOrder,
    InvalidOrderChange,
    OrderLineNotFound,
    OrderNotEditable,
    OrderNotFound,
    ReceiptUnavailable,
)
from app.modules.ordering.models import (
    Order,
    OrderLine,
    OrderNumberCounter,
    OrderType,
)
from app.modules.ordering.pricing import LineInput, PricingError, price_order
from app.modules.ordering.schemas import (
    DiscountUpdate,
    OrderCancel,
    OrderCreate,
    OrderLineInput,
    OrderLinePublic,
    OrderPublic,
    OrderSummary,
    OrderUpdate,
    ReceiptPublic,
)
from app.modules.ordering.states import (
    OPEN_STATUSES,
    OrderStatus,
    assert_transition,
)
from app.modules.settings.service import get_settings

COMPLETE_SCOPE = "order.complete"
RECEIPT_STATUSES = frozenset(
    {
        OrderStatus.CONFIRMED,
        OrderStatus.PAID,
        OrderStatus.COMPLETED,
        OrderStatus.PARTIALLY_REFUNDED,
        OrderStatus.REFUNDED,
    }
)


# Numbering


def business_today(session: Session) -> date:
    timezone = ZoneInfo(get_settings(session).timezone)
    return datetime.now(timezone).date()


def next_order_number(session: Session, business_date: date) -> str:
    """`HD-YYYYMMDD-####` from a per-day counter row, upserted under a row lock."""
    statement = (
        pg_insert(OrderNumberCounter)
        .values(business_date=business_date, last_number=1)
        .on_conflict_do_update(
            index_elements=["business_date"],
            set_={"last_number": OrderNumberCounter.last_number + 1},
        )
        .returning(col(OrderNumberCounter.last_number))
    )
    number = session.connection().execute(statement).scalar_one()
    return f"HD-{business_date:%Y%m%d}-{number:04d}"


# Loading and visibility


def can_view_all(user: User) -> bool:
    return has_permission(user, Permission.ORDERING_VIEW_ALL)


def _load(
    session: Session, order_id: uuid.UUID, actor: User, *, for_update: bool = False
) -> Order:
    query = select(Order).where(Order.id == order_id)
    if for_update:
        query = query.with_for_update().execution_options(populate_existing=True)
    order = session.exec(query).first()
    if order is None or not (can_view_all(actor) or order.cashier_id == actor.id):
        raise OrderNotFound()
    return order


def _load_open(session: Session, order_id: uuid.UUID, actor: User) -> Order:
    order = _load(session, order_id, actor, for_update=True)
    if order.status not in OPEN_STATUSES:
        raise OrderNotEditable()
    return order


def _lines(session: Session, order_id: uuid.UUID) -> list[OrderLine]:
    return list(
        session.exec(
            select(OrderLine)
            .where(OrderLine.order_id == order_id)
            .order_by(col(OrderLine.line_no))
        ).all()
    )


def to_public(session: Session, order: Order) -> OrderPublic:
    cashier = session.get(User, order.cashier_id)
    return OrderPublic.model_validate(
        {
            **order.model_dump(),
            "cashier_email": cashier.email if cashier else None,
            "cashier_name": cashier.full_name if cashier else None,
            "lines": [
                OrderLinePublic.model_validate(line)
                for line in _lines(session, order.id)
            ],
        }
    )


def get_order(session: Session, *, order_id: uuid.UUID, actor: User) -> OrderPublic:
    return to_public(session, _load(session, order_id, actor))


# Pricing


def _recalculate(session: Session, order: Order, lines: list[OrderLine]) -> None:
    """Recompute every line and order amount from snapshots; never trusts clients."""
    try:
        amounts = price_order(
            [
                LineInput(
                    unit_price=line.unit_price,
                    quantity=line.quantity,
                    discount_type=line.discount_type,
                    discount_value=line.discount_value,
                )
                for line in lines
            ],
            order_discount_type=order.order_discount_type,
            order_discount_value=order.order_discount_value,
            tax_rate=order.tax_rate,
        )
    except PricingError as exc:
        raise InvalidOrderChange(str(exc)) from exc
    now = get_datetime_utc()
    for line, result in zip(lines, amounts.lines, strict=True):
        line.discount_amount = result.discount_amount
        line.line_total = result.line_total
        line.order_discount_share = result.order_discount_share
        line.net_total = result.net_total
        line.tax_rate = order.tax_rate
        line.tax_amount = result.tax_amount
        session.add(line)
    order.subtotal = amounts.subtotal
    order.order_discount_amount = amounts.order_discount_amount
    order.discount_total = amounts.discount_total
    order.tax_total = amounts.tax_total
    order.total = amounts.total
    order.updated_at = now
    session.add(order)
    session.flush()


def _snapshot(line: OrderLine, item: MenuItem) -> None:
    line.menu_item_id = item.id
    line.item_code = item.code
    line.item_name = item.name
    line.product_type = item.product_type
    line.unit_price = item.price
    line.updated_at = get_datetime_utc()


def _apply_lines(
    session: Session, order: Order, inputs: list[OrderLineInput]
) -> list[OrderLine]:
    existing = {line.id: line for line in _lines(session, order.id)}
    kept: set[uuid.UUID] = set()
    result: list[OrderLine] = []
    for line_no, line_in in enumerate(inputs, start=1):
        if line_in.id is not None:
            line = existing.get(line_in.id)
            if line is None:
                raise OrderLineNotFound()
            if line.menu_item_id != line_in.menu_item_id:
                raise InvalidOrderChange(
                    "A line's menu item cannot change; remove it and add a new line"
                )
            if line.quantity != line_in.quantity or line.note != line_in.note:
                _snapshot(
                    line, catalog.get_sellable_item(session, line_in.menu_item_id)
                )
                line.quantity = line_in.quantity
                line.note = line_in.note
            kept.add(line.id)
        else:
            item = catalog.get_sellable_item(session, line_in.menu_item_id)
            line = OrderLine(
                order_id=order.id,
                line_no=line_no,
                menu_item_id=item.id,
                item_code=item.code,
                item_name=item.name,
                product_type=item.product_type,
                unit_price=item.price,
                quantity=line_in.quantity,
                note=line_in.note,
            )
        line.line_no = line_no
        result.append(line)
    for line_id, line in existing.items():
        if line_id not in kept:
            session.delete(line)
    for line in result:
        session.add(line)
    return result


# Use cases


def create_order(session: Session, *, data: OrderCreate, actor: User) -> OrderPublic:
    settings = get_settings(session)
    business_date = business_today(session)
    order = Order(
        number=next_order_number(session, business_date),
        business_date=business_date,
        order_type=data.order_type,
        table_label=data.table_label,
        notes=data.notes,
        tax_rate=settings.tax_rate,
        cashier_id=actor.id,
    )
    session.add(order)
    session.flush()
    lines = _apply_lines(session, order, data.lines)
    _recalculate(session, order, lines)
    audit.record(
        session,
        actor=actor,
        entity_type="order",
        entity_id=order.id,
        action="created",
        changes={"number": {"old": None, "new": order.number}},
    )
    session.commit()
    return to_public(session, order)


def update_order(
    session: Session, *, order_id: uuid.UUID, data: OrderUpdate, actor: User
) -> OrderPublic:
    order = _load_open(session, order_id, actor)
    updates = data.model_dump(exclude_unset=True)
    order_type = updates.get("order_type") or order.order_type
    if "order_type" in updates and updates["order_type"] is None:
        del updates["order_type"]
    if order_type != OrderType.DINE_IN:
        if updates.get("table_label"):
            raise InvalidOrderChange("Only dine-in orders have a table label")
        updates["table_label"] = None
    order.sqlmodel_update(updates)
    order.updated_at = get_datetime_utc()
    session.add(order)
    session.commit()
    return to_public(session, order)


def replace_lines(
    session: Session,
    *,
    order_id: uuid.UUID,
    lines: list[OrderLineInput],
    actor: User,
) -> OrderPublic:
    order = _load_open(session, order_id, actor)
    result = _apply_lines(session, order, lines)
    _recalculate(session, order, result)
    session.commit()
    return to_public(session, order)


def set_order_discount(
    session: Session, *, order_id: uuid.UUID, data: DiscountUpdate, actor: User
) -> OrderPublic:
    order = _load_open(session, order_id, actor)
    old = {"type": order.order_discount_type, "value": order.order_discount_value}
    order.order_discount_type = data.discount_type
    order.order_discount_value = data.discount_value
    order.order_discount_by_id = actor.id if data.discount_type else None
    _recalculate(session, order, _lines(session, order.id))
    audit.record(
        session,
        actor=actor,
        entity_type="order",
        entity_id=order.id,
        action="discount_changed",
        changes={
            "order_discount": {
                "old": old,
                "new": {"type": data.discount_type, "value": data.discount_value},
            },
            "discount_total": order.discount_total,
        },
    )
    session.commit()
    return to_public(session, order)


def set_line_discount(
    session: Session,
    *,
    order_id: uuid.UUID,
    line_id: uuid.UUID,
    data: DiscountUpdate,
    actor: User,
) -> OrderPublic:
    order = _load_open(session, order_id, actor)
    lines = _lines(session, order.id)
    line = next((x for x in lines if x.id == line_id), None)
    if line is None:
        raise OrderLineNotFound()
    old = {"type": line.discount_type, "value": line.discount_value}
    line.discount_type = data.discount_type
    line.discount_value = data.discount_value
    line.discount_by_id = actor.id if data.discount_type else None
    _recalculate(session, order, lines)
    audit.record(
        session,
        actor=actor,
        entity_type="order",
        entity_id=order.id,
        action="line_discount_changed",
        changes={
            "line_id": line.id,
            "item_code": line.item_code,
            "discount": {
                "old": old,
                "new": {"type": data.discount_type, "value": data.discount_value},
            },
        },
    )
    session.commit()
    return to_public(session, order)


def _transition(
    session: Session, order: Order, target: OrderStatus, actor: User, **changes: Any
) -> None:
    previous = order.status
    assert_transition(previous, target)
    order.status = target
    order.updated_at = get_datetime_utc()
    session.add(order)
    session.flush()
    audit.record(
        session,
        actor=actor,
        entity_type="order",
        entity_id=order.id,
        action=target.value,
        changes={"status": {"old": previous, "new": target}, **changes},
    )


def confirm_order(session: Session, *, order_id: uuid.UUID, actor: User) -> OrderPublic:
    order = _load(session, order_id, actor, for_update=True)
    assert_transition(order.status, OrderStatus.CONFIRMED)
    order.confirmed_at = get_datetime_utc()
    _transition(session, order, OrderStatus.CONFIRMED, actor)
    session.commit()
    return to_public(session, order)


def cancel_order(
    session: Session, *, order_id: uuid.UUID, data: OrderCancel, actor: User
) -> OrderPublic:
    order = _load(session, order_id, actor, for_update=True)
    assert_transition(order.status, OrderStatus.CANCELLED)
    order.cancelled_at = get_datetime_utc()
    order.cancelled_by_id = actor.id
    order.cancel_reason = data.reason
    _transition(session, order, OrderStatus.CANCELLED, actor, reason=data.reason)
    session.commit()
    return to_public(session, order)


CompletionStep = Callable[[Session, Order, list[OrderLine], User], None]


def _require_lines(
    _session: Session, _order: Order, lines: list[OrderLine], _actor: User
) -> None:
    if not lines:
        raise EmptyOrder("An order needs at least one line to be completed")


# Run in order inside the completion transaction. Later changes append steps
# (payment check, stock consumption); a step raises to abort completion.
COMPLETION_STEPS: list[CompletionStep] = [_require_lines]


def complete_order(
    session: Session, *, order_id: uuid.UUID, actor: User, idempotency_key: str
) -> StoredResponse:
    """Complete once; repeating `idempotency_key` returns the original result."""

    def operation() -> tuple[int, Any]:
        order = _load(session, order_id, actor, for_update=True)
        assert_transition(order.status, OrderStatus.COMPLETED)
        lines = _lines(session, order.id)
        for step in COMPLETION_STEPS:
            step(session, order, lines, actor)
        now = get_datetime_utc()
        order.completed_at = now
        order.completed_by_id = actor.id
        if order.confirmed_at is None:
            order.confirmed_at = now
        _transition(session, order, OrderStatus.COMPLETED, actor, total=order.total)
        return 200, to_public(session, order)

    return idempotency.execute(
        session,
        scope=COMPLETE_SCOPE,
        key=idempotency_key,
        payload={"order_id": str(order_id)},
        operation=operation,
    )


def get_receipt(session: Session, *, order_id: uuid.UUID, actor: User) -> ReceiptPublic:
    order = _load(session, order_id, actor)
    if order.status not in RECEIPT_STATUSES:
        raise ReceiptUnavailable()
    settings = get_settings(session)
    return ReceiptPublic(
        business_name=settings.business_name,
        currency_code=settings.currency_code,
        timezone=settings.timezone,
        order=to_public(session, order),
    )


def list_orders(
    session: Session,
    *,
    actor: User,
    number: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    status: OrderStatus | None = None,
    order_type: OrderType | None = None,
    cashier_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[OrderSummary], int]:
    """Newest first. Without view-all permission only the actor's own orders.
    Date bounds are inclusive business-timezone dates."""
    conditions: list[Any] = []
    if not can_view_all(actor):
        cashier_id = actor.id
    if cashier_id is not None:
        conditions.append(col(Order.cashier_id) == cashier_id)
    if number and number.strip():
        conditions.append(
            col(Order.number).ilike(like_pattern(number.strip()), escape="\\")
        )
    if date_from is not None:
        conditions.append(col(Order.business_date) >= date_from)
    if date_to is not None:
        conditions.append(col(Order.business_date) <= date_to)
    if status is not None:
        conditions.append(col(Order.status) == status)
    if order_type is not None:
        conditions.append(col(Order.order_type) == order_type)

    count = session.exec(
        select(func.count()).select_from(Order).where(*conditions)
    ).one()
    rows = session.exec(
        select(Order, User.email, User.full_name)
        .outerjoin(User, col(User.id) == col(Order.cashier_id))
        .where(*conditions)
        .order_by(col(Order.created_at).desc(), col(Order.number).desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return [
        OrderSummary.model_validate(
            {**order.model_dump(), "cashier_email": email, "cashier_name": name}
        )
        for order, email, name in rows
    ], count
