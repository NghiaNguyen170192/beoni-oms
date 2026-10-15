import uuid
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import Date, cast, exists, func
from sqlmodel import Session, col, select

from app.core.money import money, quantity
from app.modules.accounting.models import Expense, ExpenseCategory, RecordStatus
from app.modules.accounting.periods import period_bounds
from app.modules.accounting.service import SALE_STATUSES, financial_summary
from app.modules.catalog.models import MenuItem
from app.modules.inventory.models import (
    AdjustmentReason,
    InventoryBalance,
    InventoryItem,
    InventoryMovement,
    MovementType,
    StockAdjustmentLine,
)
from app.modules.ordering.models import Order, OrderLine
from app.modules.ordering.states import OrderStatus
from app.modules.payments.models import (
    Payment,
    PaymentMethod,
    PaymentStatus,
    Refund,
    RefundLine,
)
from app.modules.reporting.periods import GroupBy, check_range
from app.modules.settings.service import get_settings

D = Decimal
ZERO = D("0")
PERCENT = D("0.1")


def _zone(session: Session) -> str:
    return get_settings(session).timezone


def _percent(part: Decimal, whole: Decimal) -> Decimal:
    if whole == 0:
        return D("0.0")
    return (part / whole * D(100)).quantize(PERCENT, rounding=ROUND_HALF_UP)


def _change_percent(current: Decimal, previous: Decimal) -> Decimal | None:
    if previous == 0:
        return None
    return _percent(current - previous, previous)


def _bounds(session: Session, date_from: date, date_to: date) -> tuple:
    check_range(date_from, date_to)
    return period_bounds(date_from, date_to, _zone(session))


def _sale_status(status: str | None) -> OrderStatus | None:
    if status is None:
        return None
    try:
        parsed = OrderStatus(status)
    except ValueError:
        return None
    if parsed not in SALE_STATUSES:
        return OrderStatus.DRAFT
    return parsed


def _order_filters(
    *,
    cashier_id: uuid.UUID | None,
    method_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    status: str | None,
    completed: tuple | None,
):
    chosen = _sale_status(status)
    conditions = [col(Order.status).in_(SALE_STATUSES if chosen is None else (chosen,))]
    if chosen == OrderStatus.DRAFT:
        conditions = [col(Order.id).is_(None)]
    if completed is not None:
        start, end = completed
        conditions.extend([Order.completed_at >= start, Order.completed_at < end])
    if cashier_id is not None:
        conditions.append(Order.cashier_id == cashier_id)
    if method_id is not None:
        conditions.append(
            exists(
                select(Payment.id).where(
                    Payment.order_id == Order.id,
                    Payment.method_id == method_id,
                    Payment.status == PaymentStatus.ACTIVE,
                )
            )
        )
    if category_id is not None:
        conditions.append(
            exists(
                select(OrderLine.id)
                .join(MenuItem, col(MenuItem.id) == col(OrderLine.menu_item_id))
                .where(
                    OrderLine.order_id == Order.id,
                    MenuItem.category_id == category_id,
                )
            )
        )
    return conditions


def dashboard(
    session: Session, *, date_from: date, date_to: date, financial: bool
) -> dict[str, object]:
    start, end = _bounds(session, date_from, date_to)
    summary = financial_summary(session, date_from=date_from, date_to=date_to)
    count = int(
        session.exec(
            select(func.count())
            .select_from(Order)
            .where(
                col(Order.status).in_(SALE_STATUSES),
                Order.completed_at >= start,
                Order.completed_at < end,
            )
        ).one()
        or 0
    )
    net = money(summary["net_sales"])  # type: ignore[arg-type]
    low = int(
        session.exec(
            select(func.count())
            .select_from(InventoryItem)
            .join(
                InventoryBalance, col(InventoryBalance.item_id) == col(InventoryItem.id)
            )
            .where(
                col(InventoryItem.is_active).is_(True),
                InventoryItem.min_stock > 0,
                InventoryBalance.quantity <= InventoryItem.min_stock,
            )
        ).one()
        or 0
    )
    body: dict[str, object] = {
        "date_from": date_from,
        "date_to": date_to,
        "net_sales": net,
        "order_count": count,
        "average_order_value": money(net / count) if count else money(ZERO),
        "discounts": summary["discounts"],
        "refunds": summary["refunds"],
        "low_stock_count": low,
    }
    if financial:
        body.update(
            cogs=summary["cogs"],
            gross_profit=summary["gross_profit"],
            expenses=summary["expenses"],
            operating_profit=summary["operating_profit"],
        )
    return body


def _bucket(column, group_by: GroupBy, zone: str):
    return cast(func.date_trunc(group_by.value, func.timezone(zone, column)), Date)


def _line_sales(
    session: Session,
    *,
    date_from: date,
    date_to: date,
    group_by: GroupBy | None,
    cashier_id: uuid.UUID | None,
    method_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    status: str | None,
):
    start, end = _bounds(session, date_from, date_to)
    zone = _zone(session)
    gross = OrderLine.unit_price * OrderLine.quantity
    discounts = OrderLine.discount_amount + OrderLine.order_discount_share
    conditions = _order_filters(
        cashier_id=cashier_id,
        method_id=method_id,
        category_id=category_id,
        status=status,
        completed=(start, end),
    )
    if category_id is not None:
        conditions.append(MenuItem.category_id == category_id)
    bucket = _bucket(Order.completed_at, group_by or GroupBy.DAY, zone)
    columns = [
        func.coalesce(func.sum(gross), 0),
        func.coalesce(func.sum(discounts), 0),
        func.count(func.distinct(Order.id)),
    ]
    query = (
        select(*([bucket] if group_by else []), *columns)
        .select_from(Order)
        .join(OrderLine, col(OrderLine.order_id) == col(Order.id))
        .where(*conditions)
    )
    if category_id is not None:
        query = query.join(MenuItem, col(MenuItem.id) == col(OrderLine.menu_item_id))
    if group_by is not None:
        query = query.group_by(bucket).order_by(bucket)
    return start, end, zone, query


def _refund_amounts(
    session: Session,
    *,
    start,
    end,
    cashier_id: uuid.UUID | None,
    method_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    status: str | None,
) -> list[tuple[date, uuid.UUID, Decimal]]:
    """Refunds in the window as (local date, menu item, amount)."""
    conditions = _order_filters(
        cashier_id=cashier_id,
        method_id=method_id,
        category_id=None,
        status=status,
        completed=None,
    )
    conditions.extend([Refund.recorded_at >= start, Refund.recorded_at < end])
    refunds = session.exec(
        select(Refund.id, Refund.order_id, Refund.amount, Refund.recorded_at)
        .join(Order, col(Order.id) == col(Refund.order_id))
        .where(*conditions)
    ).all()
    if not refunds:
        return []
    order_ids = {row[1] for row in refunds}
    line_rows = session.exec(
        select(
            OrderLine.order_id,
            OrderLine.menu_item_id,
            OrderLine.net_total,
            MenuItem.category_id,
        )
        .join(MenuItem, col(MenuItem.id) == col(OrderLine.menu_item_id))
        .where(col(OrderLine.order_id).in_(order_ids))
    ).all()
    by_order: dict[uuid.UUID, list[tuple[uuid.UUID, Decimal, uuid.UUID]]] = defaultdict(
        list
    )
    for order_id, item_id, net, item_category in line_rows:
        by_order[order_id].append((item_id, money(net), item_category))
    explicit = session.exec(
        select(
            RefundLine.refund_id, OrderLine.menu_item_id, func.sum(RefundLine.amount)
        )
        .join(OrderLine, col(OrderLine.id) == col(RefundLine.order_line_id))
        .where(col(RefundLine.refund_id).in_([row[0] for row in refunds]))
        .group_by(RefundLine.refund_id, OrderLine.menu_item_id)
    ).all()
    explicit_map: dict[uuid.UUID, list[tuple[uuid.UUID, Decimal]]] = defaultdict(list)
    for refund_id, item_id, amount in explicit:
        explicit_map[refund_id].append((item_id, money(amount)))
    zone = _zone(session)
    allocated: list[tuple[date, uuid.UUID, Decimal]] = []
    for refund_id, order_id, amount, recorded_at in refunds:
        local_day = recorded_at.astimezone(ZoneInfo(zone)).date()
        shares = _shares(
            money(amount), by_order.get(order_id, []), explicit_map.get(refund_id)
        )
        for item_id, share, item_category in shares:
            if category_id is not None and item_category != category_id:
                continue
            if share != 0:
                allocated.append((local_day, item_id, share))
    return allocated


def _shares(
    amount: Decimal,
    lines: list[tuple[uuid.UUID, Decimal, uuid.UUID]],
    explicit: list[tuple[uuid.UUID, Decimal]] | None,
) -> list[tuple[uuid.UUID, Decimal, uuid.UUID]]:
    categories = {item_id: category for item_id, _, category in lines}
    if explicit:
        covered = sum((part for _, part in explicit), ZERO)
        shares = [
            (item_id, part, categories.get(item_id)) for item_id, part in explicit
        ]
        remainder = money(amount - covered)
        if remainder == 0 or not lines:
            return [(item, part, cat) for item, part, cat in shares if cat is not None]
        amount = remainder
    if not lines:
        return []
    total = sum((net for _, net, _ in lines), ZERO)
    parts: list[tuple[uuid.UUID, Decimal, uuid.UUID]] = []
    running = ZERO
    for item_id, net, category in lines[:-1]:
        part = money(amount * net / total) if total > 0 else money(amount / len(lines))
        parts.append((item_id, part, category))
        running += part
    last_item, _, last_category = lines[-1]
    parts.append((last_item, money(amount - running), last_category))
    if explicit:
        combined: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
        cats: dict[uuid.UUID, uuid.UUID] = {}
        for item_id, part, category in shares + parts:
            if category is None:
                continue
            combined[item_id] += part
            cats[item_id] = category
        return [
            (item_id, money(part), cats[item_id]) for item_id, part in combined.items()
        ]
    return parts


def sales_summary(
    session: Session,
    *,
    date_from: date,
    date_to: date,
    group_by: GroupBy,
    cashier_id: uuid.UUID | None = None,
    method_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    status: str | None = None,
) -> dict[str, object]:
    start, end, _, query = _line_sales(
        session,
        date_from=date_from,
        date_to=date_to,
        group_by=group_by,
        cashier_id=cashier_id,
        method_id=method_id,
        category_id=category_id,
        status=status,
    )
    grouped = {
        row[0]: (money(row[1]), money(row[2]), int(row[3]))
        for row in session.exec(query).all()
    }
    refund_rows = _refund_amounts(
        session,
        start=start,
        end=end,
        cashier_id=cashier_id,
        method_id=method_id,
        category_id=category_id,
        status=status,
    )
    refunds_by_bucket: dict[date, Decimal] = defaultdict(lambda: ZERO)
    for local_day, _, share in refund_rows:
        bucket = _truncate(local_day, group_by)
        refunds_by_bucket[bucket] += share
    keys = sorted(set(grouped) | set(refunds_by_bucket))
    data = []
    totals = [ZERO, ZERO, ZERO, 0]
    for key in keys:
        gross, discounts, count = grouped.get(key, (money(ZERO), money(ZERO), 0))
        refunded = money(refunds_by_bucket.get(key, ZERO))
        net = money(gross - discounts - refunded)
        data.append(
            {
                "period_start": key,
                "gross_sales": gross,
                "discounts": discounts,
                "refunds": refunded,
                "net_sales": net,
                "order_count": count,
                "average_order_value": money(net / count) if count else money(ZERO),
            }
        )
        totals[0] += gross
        totals[1] += discounts
        totals[2] += refunded
        totals[3] += count
    gross_total, discount_total, refund_total, order_count = totals
    net_total = money(gross_total - discount_total - refund_total)
    return {
        "date_from": date_from,
        "date_to": date_to,
        "group_by": group_by,
        "gross_sales": money(gross_total),
        "discounts": money(discount_total),
        "refunds": money(refund_total),
        "net_sales": net_total,
        "order_count": order_count,
        "average_order_value": money(net_total / order_count)
        if order_count
        else money(ZERO),
        "data": data,
        "payments": payment_breakdown(
            session,
            start=start,
            end=end,
            cashier_id=cashier_id,
            method_id=method_id,
            category_id=category_id,
            status=status,
        ),
    }


def _truncate(day: date, group_by: GroupBy) -> date:
    if group_by == GroupBy.MONTH:
        return day.replace(day=1)
    if group_by == GroupBy.WEEK:
        return day.fromordinal(day.toordinal() - day.weekday())
    return day


def payment_breakdown(
    session: Session,
    *,
    start,
    end,
    cashier_id: uuid.UUID | None,
    method_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    status: str | None,
) -> list[dict[str, object]]:
    conditions = _order_filters(
        cashier_id=cashier_id,
        method_id=None,
        category_id=category_id,
        status=status,
        completed=None,
    )
    pay_filters = [
        Payment.status == PaymentStatus.ACTIVE,
        Payment.recorded_at >= start,
        Payment.recorded_at < end,
        *conditions,
    ]
    if method_id is not None:
        pay_filters.append(Payment.method_id == method_id)
    paid = session.exec(
        select(
            PaymentMethod.id,
            PaymentMethod.name,
            func.coalesce(func.sum(Payment.amount), 0),
        )
        .join(Payment, col(Payment.method_id) == col(PaymentMethod.id))
        .join(Order, col(Order.id) == col(Payment.order_id))
        .where(*pay_filters)
        .group_by(PaymentMethod.id, PaymentMethod.name)
    ).all()
    refund_filters = [
        Refund.recorded_at >= start,
        Refund.recorded_at < end,
        *conditions,
    ]
    if method_id is not None:
        refund_filters.append(Refund.method_id == method_id)
    refunded = dict(
        session.exec(
            select(Refund.method_id, func.coalesce(func.sum(Refund.amount), 0))
            .join(Order, col(Order.id) == col(Refund.order_id))
            .where(*refund_filters)
            .group_by(Refund.method_id)
        ).all()
    )
    names = {row[0]: row[1] for row in paid}
    amounts = {row[0]: money(row[2]) for row in paid}
    if refunded:
        missing = [item for item in refunded if item not in names]
        if missing:
            extra = session.exec(
                select(PaymentMethod.id, PaymentMethod.name).where(
                    col(PaymentMethod.id).in_(missing)
                )
            ).all()
            names.update(dict(extra))
    rows = []
    for method, name in sorted(names.items(), key=lambda item: item[1]):
        rows.append(
            {
                "method_id": method,
                "method_name": name,
                "amount": money(
                    amounts.get(method, ZERO) - money(refunded.get(method, ZERO))
                ),
            }
        )
    return rows


def product_performance(
    session: Session,
    *,
    date_from: date,
    date_to: date,
    cashier_id: uuid.UUID | None = None,
    method_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    status: str | None = None,
    sort: str = "quantity",
    financial: bool = False,
) -> dict[str, object]:
    start, end = _bounds(session, date_from, date_to)
    gross = OrderLine.unit_price * OrderLine.quantity
    discounts = OrderLine.discount_amount + OrderLine.order_discount_share
    conditions = _order_filters(
        cashier_id=cashier_id,
        method_id=method_id,
        category_id=category_id,
        status=status,
        completed=(start, end),
    )
    item_query = (
        select(
            OrderLine.menu_item_id,
            func.coalesce(func.max(MenuItem.name), func.max(OrderLine.item_name)),
            func.coalesce(func.sum(OrderLine.quantity), 0),
            func.coalesce(func.sum(gross), 0),
            func.coalesce(func.sum(discounts), 0),
            func.coalesce(func.sum(OrderLine.net_total), 0),
            func.coalesce(func.sum(OrderLine.cogs_amount), 0),
        )
        .select_from(Order)
        .join(OrderLine, col(OrderLine.order_id) == col(Order.id))
        .outerjoin(MenuItem, col(MenuItem.id) == col(OrderLine.menu_item_id))
        .where(*conditions)
        .group_by(OrderLine.menu_item_id)
    )
    if category_id is not None:
        item_query = item_query.where(MenuItem.category_id == category_id)
    products: dict[uuid.UUID, dict[str, object]] = {}
    for (
        item_id,
        name,
        qty,
        gross_amount,
        discount_amount,
        net_amount,
        cost,
    ) in session.exec(item_query).all():
        products[item_id] = {
            "menu_item_id": item_id,
            "name": name,
            "quantity": quantity(qty),
            "gross_sales": money(gross_amount),
            "discounts": money(discount_amount),
            "net_before_refund": money(net_amount),
            "estimated_cost": money(cost),
        }
    for _, item_id, share in _refund_amounts(
        session,
        start=start,
        end=end,
        cashier_id=cashier_id,
        method_id=method_id,
        category_id=category_id,
        status=status,
    ):
        row = products.get(item_id)
        if row is None:
            item = session.get(MenuItem, item_id)
            row = {
                "menu_item_id": item_id,
                "name": item.name if item else str(item_id),
                "quantity": quantity(ZERO),
                "gross_sales": money(ZERO),
                "discounts": money(ZERO),
                "net_before_refund": money(ZERO),
                "estimated_cost": money(ZERO),
                "refunds": ZERO,
            }
            products[item_id] = row
        row["refunds"] = money(row.get("refunds", ZERO) + share)  # type: ignore[operator]
    data = []
    net_total = ZERO
    for row in products.values():
        refunded = money(row.get("refunds", ZERO))  # type: ignore[arg-type]
        net = money(row["net_before_refund"] - refunded)  # type: ignore[operator]
        row["net_sales"] = net
        net_total += net
        data.append(row)
    net_total = money(net_total)
    for row in data:
        row["share"] = _percent(row["net_sales"], net_total)  # type: ignore[arg-type]
        if financial:
            row["estimated_gross_profit"] = money(
                row["net_sales"] - row["estimated_cost"]
            )  # type: ignore[operator]
        else:
            row.pop("estimated_cost", None)
        row.pop("net_before_refund", None)
        row.pop("refunds", None)
    reverse = sort != "name"
    key_name = sort if sort in {"quantity", "net_sales", "gross_sales"} else "quantity"
    data.sort(key=lambda row: row[key_name], reverse=reverse)  # type: ignore[arg-type, return-value]
    if data:
        data[0]["best_seller"] = True
        data[-1]["least_seller"] = True
    return {
        "date_from": date_from,
        "date_to": date_to,
        "net_sales": net_total,
        "data": data,
    }


def movement_summary(
    session: Session,
    *,
    date_from: date,
    date_to: date,
    category_id: uuid.UUID | None = None,
    item_type: str | None = None,
    is_active: bool | None = None,
) -> dict[str, object]:
    start, end = _bounds(session, date_from, date_to)
    item_filters = []
    if category_id is not None:
        item_filters.append(InventoryItem.category_id == category_id)
    if item_type is not None:
        item_filters.append(InventoryItem.item_type == item_type)
    if is_active is not None:
        item_filters.append(col(InventoryItem.is_active).is_(is_active))
    items = session.exec(
        select(InventoryItem, InventoryBalance)
        .join(InventoryBalance, col(InventoryBalance.item_id) == col(InventoryItem.id))
        .where(*item_filters)
        .order_by(InventoryItem.name)
    ).all()
    opening = dict(
        session.exec(
            select(
                InventoryMovement.item_id,
                func.coalesce(func.sum(InventoryMovement.quantity), 0),
            )
            .where(InventoryMovement.occurred_at < start)
            .group_by(InventoryMovement.item_id)
        ).all()
    )
    typed = session.exec(
        select(
            InventoryMovement.item_id,
            InventoryMovement.movement_type,
            func.coalesce(func.sum(InventoryMovement.quantity), 0),
        )
        .where(
            InventoryMovement.occurred_at >= start, InventoryMovement.occurred_at < end
        )
        .group_by(InventoryMovement.item_id, InventoryMovement.movement_type)
    ).all()
    by_type: dict[tuple[uuid.UUID, str], Decimal] = {
        (
            item_id,
            movement_type.value if hasattr(movement_type, "value") else movement_type,
        ): quantity(total)
        for item_id, movement_type, total in typed
    }
    reasons = session.exec(
        select(
            StockAdjustmentLine.item_id,
            StockAdjustmentLine.reason,
            func.coalesce(func.sum(InventoryMovement.quantity), 0),
        )
        .join(
            InventoryMovement,
            col(InventoryMovement.id) == col(StockAdjustmentLine.movement_id),
        )
        .where(
            InventoryMovement.occurred_at >= start, InventoryMovement.occurred_at < end
        )
        .group_by(StockAdjustmentLine.item_id, StockAdjustmentLine.reason)
    ).all()
    by_reason: dict[tuple[uuid.UUID, str], Decimal] = {
        (item_id, reason.value if hasattr(reason, "value") else reason): quantity(total)
        for item_id, reason, total in reasons
    }
    data = []
    for item, balance in items:
        received = by_type.get((item.id, MovementType.RECEIPT.value), quantity(ZERO))
        consumed = quantity(
            -by_type.get((item.id, MovementType.SALE_CONSUMPTION.value), quantity(ZERO))
        )
        adjustments = by_type.get(
            (item.id, MovementType.ADJUSTMENT.value), quantity(ZERO)
        )
        returns = by_type.get((item.id, MovementType.RETURN.value), quantity(ZERO))
        reversals = by_type.get((item.id, MovementType.REVERSAL.value), quantity(ZERO))
        opened = quantity(opening.get(item.id, ZERO))
        closing = quantity(
            opened + received - consumed + adjustments + returns + reversals
        )
        data.append(
            {
                "item_id": item.id,
                "sku": item.sku,
                "name": item.name,
                "base_unit": item.base_unit.value,
                "opening": opened,
                "received": received,
                "consumed": consumed,
                "adjustments": adjustments,
                "spoilage": by_reason.get(
                    (item.id, AdjustmentReason.SPOILAGE.value), quantity(ZERO)
                ),
                "expired": by_reason.get(
                    (item.id, AdjustmentReason.EXPIRED.value), quantity(ZERO)
                ),
                "damaged": by_reason.get(
                    (item.id, AdjustmentReason.DAMAGED.value), quantity(ZERO)
                ),
                "missing": by_reason.get(
                    (item.id, AdjustmentReason.MISSING.value), quantity(ZERO)
                ),
                "physical_count": by_reason.get(
                    (item.id, AdjustmentReason.PHYSICAL_COUNT.value), quantity(ZERO)
                ),
                "correction": by_reason.get(
                    (item.id, AdjustmentReason.CORRECTION.value), quantity(ZERO)
                ),
                "returns": returns,
                "reversals": reversals,
                "closing": closing,
                "closing_value": money(closing * balance.avg_unit_cost),
            }
        )
    return {
        "date_from": date_from,
        "date_to": date_to,
        "data": data,
        "count": len(data),
    }


def stock_status(
    session: Session,
    *,
    category_id: uuid.UUID | None = None,
    item_type: str | None = None,
    is_active: bool | None = None,
) -> dict[str, object]:
    filters = []
    if category_id is not None:
        filters.append(InventoryItem.category_id == category_id)
    if item_type is not None:
        filters.append(InventoryItem.item_type == item_type)
    if is_active is not None:
        filters.append(col(InventoryItem.is_active).is_(is_active))
    rows = session.exec(
        select(InventoryItem, InventoryBalance)
        .join(InventoryBalance, col(InventoryBalance.item_id) == col(InventoryItem.id))
        .where(*filters)
        .order_by(InventoryItem.name)
    ).all()
    total = ZERO
    low: list[dict[str, object]] = []
    negative: list[dict[str, object]] = []
    for item, balance in rows:
        if balance.quantity >= 0:
            total += balance.quantity * balance.avg_unit_cost
        entry = {
            "item_id": item.id,
            "sku": item.sku,
            "name": item.name,
            "quantity": quantity(balance.quantity),
            "base_unit": item.base_unit.value,
        }
        if balance.quantity < 0:
            negative.append(entry)
        elif (
            item.is_active and item.min_stock > 0 and balance.quantity <= item.min_stock
        ):
            low.append(entry)
    return {"total_value": money(total), "low_stock": low, "negative_stock": negative}


def expense_breakdown(
    session: Session, *, date_from: date, date_to: date
) -> dict[str, object]:
    check_range(date_from, date_to)
    rows = session.exec(
        select(
            ExpenseCategory.id,
            ExpenseCategory.name,
            func.coalesce(func.sum(Expense.amount), 0),
        )
        .join(Expense, col(Expense.category_id) == col(ExpenseCategory.id))
        .where(
            Expense.status == RecordStatus.RECORDED,
            Expense.expense_date >= date_from,
            Expense.expense_date <= date_to,
        )
        .group_by(ExpenseCategory.id, ExpenseCategory.name)
        .order_by(ExpenseCategory.name)
    ).all()
    total = money(sum((money(amount) for _, _, amount in rows), ZERO))
    return {
        "date_from": date_from,
        "date_to": date_to,
        "total": total,
        "data": [
            {
                "category_id": category_id,
                "category_name": name,
                "amount": money(amount),
                "share": _percent(money(amount), total),
            }
            for category_id, name, amount in rows
        ],
    }


def profit_statement(
    session: Session, *, date_from: date, date_to: date
) -> dict[str, object]:
    check_range(date_from, date_to)
    summary = financial_summary(session, date_from=date_from, date_to=date_to)
    net = money(summary["net_sales"])  # type: ignore[arg-type]
    gross_profit = money(summary["gross_profit"])  # type: ignore[arg-type]
    return {
        "date_from": date_from,
        "date_to": date_to,
        "net_sales": net,
        "cogs": summary["cogs"],
        "gross_profit": gross_profit,
        "gross_margin": _percent(gross_profit, net),
        "expenses": summary["expenses"],
        "operating_profit": summary["operating_profit"],
        "estimate": True,
        "note": "Management estimate, not statutory accounts",
        "uncertain_cost_lines": summary["uncertain_cost_lines"],
        "missing_cost_lines": summary["missing_cost_lines"],
    }


def profit_comparison(
    session: Session,
    *,
    date_from: date,
    date_to: date,
    compare_from: date | None = None,
    compare_to: date | None = None,
) -> dict[str, object]:
    from app.modules.reporting.periods import previous_period

    check_range(date_from, date_to)
    if compare_from is None or compare_to is None:
        compare_from, compare_to = previous_period(date_from, date_to)
    check_range(compare_from, compare_to)
    current = profit_statement(session, date_from=date_from, date_to=date_to)
    previous = profit_statement(session, date_from=compare_from, date_to=compare_to)
    keys = (
        "net_sales",
        "cogs",
        "gross_profit",
        "expenses",
        "operating_profit",
    )
    lines = []
    for key in keys:
        now = money(current[key])  # type: ignore[arg-type]
        then = money(previous[key])  # type: ignore[arg-type]
        lines.append(
            {
                "key": key,
                "current": now,
                "previous": then,
                "change": money(now - then),
                "change_percent": _change_percent(now, then),
            }
        )
    return {
        "date_from": date_from,
        "date_to": date_to,
        "compare_from": compare_from,
        "compare_to": compare_to,
        "lines": lines,
        "note": current["note"],
        "uncertain_cost_lines": current["uncertain_cost_lines"],
        "missing_cost_lines": current["missing_cost_lines"],
    }
