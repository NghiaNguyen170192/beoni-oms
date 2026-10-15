import uuid
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, or_, select

from app.core.errors import Invalid, violated_constraint
from app.core.money import money, quantity, unit_cost
from app.models import User, get_datetime_utc
from app.modules.audit import service as audit
from app.modules.idempotency import service as idempotency
from app.modules.idempotency.service import StoredResponse
from app.modules.inventory.errors import InventoryItemNotFound, ItemInactive
from app.modules.inventory.models import InventoryItem, MovementType
from app.modules.inventory.service import MovementLine, post_movements
from app.modules.purchasing.errors import (
    ReceiptAlreadyPosted,
    ReceiptHasNoLines,
    ReceiptHasPayments,
    ReceiptNotDraft,
    ReceiptNotFound,
    ReceiptNotPosted,
    ReceiptReferenceTaken,
    SupplierCodeTaken,
    SupplierHasReceipts,
    SupplierInactive,
    SupplierNotFound,
)
from app.modules.purchasing.models import (
    SUPPLIER_CODE_INDEX,
    PayableStatus,
    ReceiptPaymentStatus,
    ReceiptReferenceCounter,
    ReceiptStatus,
    StockReceipt,
    StockReceiptLine,
    Supplier,
    SupplierPayable,
)
from app.modules.purchasing.schemas import (
    PayablePublic,
    ReceiptCreate,
    ReceiptLinePublic,
    ReceiptReverse,
    ReceiptSummary,
    ReceiptUpdate,
    StockReceiptPublic,
    SupplierBalance,
    SupplierCreate,
    SupplierPublic,
    SupplierUpdate,
)
from app.modules.settings.service import get_settings

RECEIPT_SOURCE = "stock_receipt"
POST_SCOPE = "purchasing.receipt.post"
REVERSE_SCOPE = "purchasing.receipt.reverse"
_SUPPLIER_FIELDS = (
    "name",
    "code",
    "phone",
    "email",
    "address",
    "tax_code",
    "contact_person",
    "notes",
    "is_active",
)


def _like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def business_today(session: Session) -> date:
    timezone = ZoneInfo(get_settings(session).timezone)
    return datetime.now(timezone).date()


def next_receipt_reference(session: Session, business_date: date) -> str:
    """`PN-YYYYMMDD-####` from a per-day counter row, upserted under a row lock."""
    statement = (
        pg_insert(ReceiptReferenceCounter)
        .values(business_date=business_date, last_number=1)
        .on_conflict_do_update(
            index_elements=["business_date"],
            set_={"last_number": ReceiptReferenceCounter.last_number + 1},
        )
        .returning(col(ReceiptReferenceCounter.last_number))
    )
    number = session.connection().execute(statement).scalar_one()
    return f"PN-{business_date:%Y%m%d}-{number:04d}"


def payment_status_of(payable: SupplierPayable | None) -> ReceiptPaymentStatus:
    if (
        payable is None
        or payable.status == PayableStatus.CANCELLED
        or payable.paid_amount <= 0
    ):
        return ReceiptPaymentStatus.UNPAID
    if payable.amount > 0 and payable.paid_amount >= payable.amount:
        return ReceiptPaymentStatus.PAID
    return ReceiptPaymentStatus.PARTIALLY_PAID


def refresh_payable_status(payable: SupplierPayable) -> None:
    """Keep payable status consistent with amounts. Does not touch cancelled rows."""
    if payable.status == PayableStatus.CANCELLED:
        return
    if payable.paid_amount <= 0:
        payable.status = PayableStatus.UNPAID
    elif payable.amount > 0 and payable.paid_amount >= payable.amount:
        payable.status = PayableStatus.PAID
    else:
        payable.status = PayableStatus.PARTIALLY_PAID


# Suppliers


def _supplier_or_404(session: Session, supplier_id: uuid.UUID) -> Supplier:
    supplier = session.get(Supplier, supplier_id)
    if supplier is None:
        raise SupplierNotFound()
    return supplier


def _balances(
    session: Session, supplier_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[Decimal, Decimal]]:
    if not supplier_ids:
        return {}
    rows = session.exec(
        select(
            SupplierPayable.supplier_id,
            func.coalesce(func.sum(SupplierPayable.amount), 0),
            func.coalesce(func.sum(SupplierPayable.paid_amount), 0),
        )
        .where(
            col(SupplierPayable.supplier_id).in_(supplier_ids),
            SupplierPayable.status != PayableStatus.CANCELLED,
        )
        .group_by(col(SupplierPayable.supplier_id))
    ).all()
    return {
        supplier_id: (Decimal(payables), Decimal(paid))
        for supplier_id, payables, paid in rows
    }


def _supplier_public(
    supplier: Supplier, totals: tuple[Decimal, Decimal] | None = None
) -> SupplierPublic:
    payables, paid = totals or (Decimal("0"), Decimal("0"))
    return SupplierPublic.model_validate(
        {
            **supplier.model_dump(),
            "payables_total": payables,
            "paid_total": paid,
            "outstanding": payables - paid,
        }
    )


def create_supplier(
    session: Session, *, data: SupplierCreate, actor: User
) -> SupplierPublic:
    supplier = Supplier(**data.model_dump())
    session.add(supplier)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        if violated_constraint(exc) == SUPPLIER_CODE_INDEX:
            raise SupplierCodeTaken() from exc
        raise
    audit.record(
        session,
        actor=actor,
        entity_type="supplier",
        entity_id=supplier.id,
        action="created",
        changes={"name": supplier.name, "code": supplier.code},
    )
    session.commit()
    session.refresh(supplier)
    return _supplier_public(supplier)


def update_supplier(
    session: Session, *, supplier_id: uuid.UUID, data: SupplierUpdate, actor: User
) -> SupplierPublic:
    supplier = _supplier_or_404(session, supplier_id)
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes and not changes["name"]:
        raise Invalid("Name must not be blank")
    before = {field: getattr(supplier, field) for field in changes}
    for field, value in changes.items():
        setattr(supplier, field, value)
    supplier.updated_at = get_datetime_utc()
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        if violated_constraint(exc) == SUPPLIER_CODE_INDEX:
            raise SupplierCodeTaken() from exc
        raise
    audit.record(
        session,
        actor=actor,
        entity_type="supplier",
        entity_id=supplier.id,
        action="updated",
        changes=audit.diff(before, changes, changes),
    )
    session.commit()
    session.refresh(supplier)
    totals = _balances(session, [supplier.id]).get(supplier.id)
    return _supplier_public(supplier, totals)


def delete_supplier(session: Session, *, supplier_id: uuid.UUID, actor: User) -> None:
    supplier = _supplier_or_404(session, supplier_id)
    referenced = session.exec(
        select(func.count())
        .select_from(StockReceipt)
        .where(StockReceipt.supplier_id == supplier_id)
    ).one()
    if referenced:
        raise SupplierHasReceipts()
    session.delete(supplier)
    audit.record(
        session,
        actor=actor,
        entity_type="supplier",
        entity_id=supplier_id,
        action="deleted",
    )
    session.commit()


def get_supplier(session: Session, supplier_id: uuid.UUID) -> SupplierPublic:
    supplier = _supplier_or_404(session, supplier_id)
    totals = _balances(session, [supplier.id]).get(supplier.id)
    return _supplier_public(supplier, totals)


def list_suppliers(
    session: Session,
    *,
    q: str | None = None,
    is_active: bool | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[SupplierPublic], int]:
    conditions = []
    if q:
        pattern = _like(q)
        conditions.append(
            or_(
                col(Supplier.name).ilike(pattern, escape="\\"),
                col(Supplier.code).ilike(pattern, escape="\\"),
                col(Supplier.phone).ilike(pattern, escape="\\"),
            )
        )
    if is_active is not None:
        conditions.append(col(Supplier.is_active) == is_active)
    count = session.exec(
        select(func.count()).select_from(Supplier).where(*conditions)
    ).one()
    rows = session.exec(
        select(Supplier)
        .where(*conditions)
        .order_by(col(Supplier.name))
        .offset(skip)
        .limit(limit)
    ).all()
    totals = _balances(session, [row.id for row in rows])
    return [_supplier_public(row, totals.get(row.id)) for row in rows], count


def supplier_balance(session: Session, supplier_id: uuid.UUID) -> SupplierBalance:
    _supplier_or_404(session, supplier_id)
    payables, paid = _balances(session, [supplier_id]).get(
        supplier_id, (Decimal("0"), Decimal("0"))
    )
    return SupplierBalance(
        supplier_id=supplier_id,
        payables_total=payables,
        paid_total=paid,
        outstanding=payables - paid,
    )


def supplier_history(
    session: Session,
    supplier_id: uuid.UUID,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[ReceiptSummary], int]:
    _supplier_or_404(session, supplier_id)
    return list_receipts(
        session,
        supplier_id=supplier_id,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )


# Receipts


def _active_supplier(session: Session, supplier_id: uuid.UUID) -> Supplier:
    supplier = _supplier_or_404(session, supplier_id)
    if not supplier.is_active:
        raise SupplierInactive()
    return supplier


def _items(
    session: Session, item_ids: list[uuid.UUID]
) -> dict[uuid.UUID, InventoryItem]:
    ids = set(item_ids)
    rows = session.exec(
        select(InventoryItem).where(col(InventoryItem.id).in_(ids))
    ).all()
    if len(rows) != len(ids):
        raise InventoryItemNotFound()
    return {row.id: row for row in rows}


def _build_line(
    receipt_id: uuid.UUID,
    line_no: int,
    item: InventoryItem,
    purchase_qty: Decimal,
    purchase_unit_cost: Decimal,
    *,
    sign: int = 1,
) -> StockReceiptLine:
    qty = quantity(purchase_qty.copy_abs() * sign)
    cost = money(purchase_unit_cost)
    factor = item.conversion_factor
    base_qty = quantity(qty * factor)
    base_cost = unit_cost(cost / factor)
    return StockReceiptLine(
        receipt_id=receipt_id,
        line_no=line_no,
        item_id=item.id,
        purchase_qty=qty,
        purchase_unit_cost=cost,
        base_qty=base_qty,
        base_unit_cost=base_cost,
        line_total=money(qty * cost),
    )


def _replace_lines(
    session: Session,
    receipt: StockReceipt,
    lines: list,
    items: dict[uuid.UUID, InventoryItem],
) -> None:
    existing = session.exec(
        select(StockReceiptLine).where(StockReceiptLine.receipt_id == receipt.id)
    ).all()
    for row in existing:
        session.delete(row)
    session.flush()
    total = Decimal("0")
    for line_no, line in enumerate(lines, start=1):
        row = _build_line(
            receipt.id,
            line_no,
            items[line.item_id],
            line.purchase_quantity,
            line.purchase_unit_cost,
        )
        total += row.line_total
        session.add(row)
    receipt.total_value = money(total)


def _payable_for(
    session: Session, receipt_id: uuid.UUID, *, for_update: bool = False
) -> SupplierPayable | None:
    query = select(SupplierPayable).where(SupplierPayable.receipt_id == receipt_id)
    if for_update:
        query = query.with_for_update().execution_options(populate_existing=True)
    return session.exec(query).first()


def _line_public(line: StockReceiptLine, item: InventoryItem) -> ReceiptLinePublic:
    return ReceiptLinePublic(
        id=line.id,
        line_no=line.line_no,
        item_id=line.item_id,
        item_sku=item.sku,
        item_name=item.name,
        purchase_unit=item.purchase_unit.value,
        base_unit=item.base_unit.value,
        purchase_qty=line.purchase_qty,
        purchase_unit_cost=line.purchase_unit_cost,
        base_qty=line.base_qty,
        base_unit_cost=line.base_unit_cost,
        line_total=line.line_total,
    )


def _receipt_public(session: Session, receipt: StockReceipt) -> StockReceiptPublic:
    supplier = session.get(Supplier, receipt.supplier_id)
    assert supplier is not None
    rows = session.exec(
        select(StockReceiptLine, InventoryItem)
        .join(InventoryItem, col(InventoryItem.id) == col(StockReceiptLine.item_id))
        .where(StockReceiptLine.receipt_id == receipt.id)
        .order_by(col(StockReceiptLine.line_no))
    ).all()
    payable = _payable_for(session, receipt.id)
    return StockReceiptPublic.model_validate(
        {
            **receipt.model_dump(),
            "supplier_name": supplier.name,
            "payment_status": payment_status_of(payable),
            "lines": [_line_public(line, item) for line, item in rows],
        }
    )


def _summary(
    receipt: StockReceipt, supplier_name: str, payable: SupplierPayable | None
) -> ReceiptSummary:
    return ReceiptSummary(
        id=receipt.id,
        reference=receipt.reference,
        supplier_id=receipt.supplier_id,
        supplier_name=supplier_name,
        receipt_date=receipt.receipt_date,
        status=receipt.status,
        payment_status=payment_status_of(payable),
        total_value=receipt.total_value,
        posted_at=receipt.posted_at,
    )


def create_receipt(
    session: Session, *, data: ReceiptCreate, actor: User
) -> StockReceiptPublic:
    supplier = _active_supplier(session, data.supplier_id)
    items = _items(session, [line.item_id for line in data.lines])
    reference = data.reference or next_receipt_reference(
        session, business_today(session)
    )
    receipt = StockReceipt(
        reference=reference,
        supplier_id=supplier.id,
        receipt_date=data.receipt_date,
        notes=data.notes,
        created_by_id=actor.id,
    )
    session.add(receipt)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ReceiptReferenceTaken() from exc
    _replace_lines(session, receipt, data.lines, items)
    audit.record(
        session,
        actor=actor,
        entity_type=RECEIPT_SOURCE,
        entity_id=receipt.id,
        action="created",
        changes={"reference": receipt.reference, "total": receipt.total_value},
    )
    session.commit()
    session.refresh(receipt)
    return _receipt_public(session, receipt)


def update_receipt(
    session: Session, *, receipt_id: uuid.UUID, data: ReceiptUpdate, actor: User
) -> StockReceiptPublic:
    receipt = session.get(StockReceipt, receipt_id)
    if receipt is None:
        raise ReceiptNotFound()
    if receipt.status != ReceiptStatus.DRAFT:
        raise ReceiptNotDraft()
    changes = data.model_dump(exclude_unset=True)
    changes.pop("total", None)
    lines = changes.pop("lines", None)
    if "supplier_id" in changes:
        _active_supplier(session, changes["supplier_id"])
    if "reference" in changes and not changes["reference"]:
        changes.pop("reference")
    for field, value in changes.items():
        setattr(receipt, field, value)
    if lines is not None:
        parsed = ReceiptCreate.model_validate(
            {
                "supplier_id": receipt.supplier_id,
                "receipt_date": receipt.receipt_date,
                "lines": lines,
            }
        )
        items = _items(session, [line.item_id for line in parsed.lines])
        _replace_lines(session, receipt, parsed.lines, items)
    receipt.updated_at = get_datetime_utc()
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ReceiptReferenceTaken() from exc
    audit.record(
        session,
        actor=actor,
        entity_type=RECEIPT_SOURCE,
        entity_id=receipt.id,
        action="updated",
    )
    session.commit()
    session.refresh(receipt)
    return _receipt_public(session, receipt)


def delete_receipt(session: Session, *, receipt_id: uuid.UUID, actor: User) -> None:
    receipt = session.get(StockReceipt, receipt_id)
    if receipt is None:
        raise ReceiptNotFound()
    if receipt.status != ReceiptStatus.DRAFT:
        raise ReceiptNotDraft()
    session.delete(receipt)
    audit.record(
        session,
        actor=actor,
        entity_type=RECEIPT_SOURCE,
        entity_id=receipt_id,
        action="deleted",
        changes={"reference": receipt.reference},
    )
    session.commit()


def get_receipt(session: Session, receipt_id: uuid.UUID) -> StockReceiptPublic:
    receipt = session.get(StockReceipt, receipt_id)
    if receipt is None:
        raise ReceiptNotFound()
    return _receipt_public(session, receipt)


def list_receipts(
    session: Session,
    *,
    supplier_id: uuid.UUID | None = None,
    status: ReceiptStatus | None = None,
    payment_status: ReceiptPaymentStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[ReceiptSummary], int]:
    conditions = []
    if supplier_id is not None:
        conditions.append(col(StockReceipt.supplier_id) == supplier_id)
    if status is not None:
        conditions.append(col(StockReceipt.status) == status)
    if date_from is not None:
        conditions.append(col(StockReceipt.receipt_date) >= date_from)
    if date_to is not None:
        conditions.append(col(StockReceipt.receipt_date) <= date_to)
    if q:
        conditions.append(col(StockReceipt.reference).ilike(_like(q), escape="\\"))
    rows = session.exec(
        select(StockReceipt, Supplier.name, SupplierPayable)
        .join(Supplier, col(Supplier.id) == col(StockReceipt.supplier_id))
        .outerjoin(
            SupplierPayable, col(SupplierPayable.receipt_id) == col(StockReceipt.id)
        )
        .where(*conditions)
        .order_by(
            col(StockReceipt.receipt_date).desc(), col(StockReceipt.created_at).desc()
        )
    ).all()
    summaries = [_summary(receipt, name, payable) for receipt, name, payable in rows]
    if payment_status is not None:
        summaries = [row for row in summaries if row.payment_status == payment_status]
    count = len(summaries)
    return summaries[skip : skip + limit], count


def _lock_receipt(session: Session, receipt_id: uuid.UUID) -> StockReceipt:
    receipt = session.exec(
        select(StockReceipt)
        .where(StockReceipt.id == receipt_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if receipt is None:
        raise ReceiptNotFound()
    return receipt


def _lines_of(session: Session, receipt_id: uuid.UUID) -> list[StockReceiptLine]:
    return list(
        session.exec(
            select(StockReceiptLine)
            .where(StockReceiptLine.receipt_id == receipt_id)
            .order_by(col(StockReceiptLine.line_no))
        ).all()
    )


def post_receipt(
    session: Session,
    *,
    receipt_id: uuid.UUID,
    actor: User,
    idempotency_key: str,
    payment_amount: Decimal | None = None,
    account_id: uuid.UUID | None = None,
) -> StoredResponse:
    payload = {
        "receipt_id": str(receipt_id),
        "payment_amount": str(payment_amount) if payment_amount is not None else None,
        "account_id": str(account_id) if account_id else None,
    }

    def operation() -> tuple[int, StockReceiptPublic]:
        receipt = _lock_receipt(session, receipt_id)
        if receipt.status != ReceiptStatus.DRAFT:
            raise ReceiptAlreadyPosted()
        supplier = _supplier_or_404(session, receipt.supplier_id)
        if not supplier.is_active:
            raise SupplierInactive()
        lines = _lines_of(session, receipt.id)
        if not lines:
            raise ReceiptHasNoLines()
        items = _items(session, [line.item_id for line in lines])
        for item in items.values():
            if not item.is_active:
                raise ItemInactive(f"Inventory item {item.sku} is inactive")
        refreshed: list[StockReceiptLine] = []
        for line in lines:
            rebuilt = _build_line(
                receipt.id,
                line.line_no,
                items[line.item_id],
                line.purchase_qty,
                line.purchase_unit_cost,
            )
            line.base_qty = rebuilt.base_qty
            line.base_unit_cost = rebuilt.base_unit_cost
            line.line_total = rebuilt.line_total
            refreshed.append(line)
        receipt.total_value = money(
            sum((line.line_total for line in refreshed), Decimal("0"))
        )
        post_movements(
            session,
            lines=[
                MovementLine(
                    item_id=line.item_id,
                    quantity=line.base_qty,
                    unit_cost=line.base_unit_cost,
                )
                for line in refreshed
            ],
            movement_type=MovementType.RECEIPT,
            source_type=RECEIPT_SOURCE,
            source_id=receipt.id,
            actor=actor,
        )
        now = get_datetime_utc()
        receipt.status = ReceiptStatus.POSTED
        receipt.posted_at = now
        receipt.posted_by_id = actor.id
        receipt.updated_at = now
        payable = SupplierPayable(
            receipt_id=receipt.id,
            supplier_id=receipt.supplier_id,
            amount=receipt.total_value,
            paid_amount=Decimal("0"),
            status=(
                PayableStatus.UNPAID
                if receipt.total_value == 0
                else PayableStatus.UNPAID
            ),
        )
        session.add(payable)
        session.flush()
        if payment_amount is not None:
            if account_id is None:
                raise Invalid("A payment account is required")
            from app.modules.accounting.service import apply_supplier_payment

            apply_supplier_payment(
                session,
                supplier_id=receipt.supplier_id,
                amount=payment_amount,
                payment_date=receipt.receipt_date,
                account_id=account_id,
                allocations=[(payable.id, payment_amount)],
                reference=receipt.reference,
                actor=actor,
            )
        audit.record(
            session,
            actor=actor,
            entity_type=RECEIPT_SOURCE,
            entity_id=receipt.id,
            action="posted",
            changes={"total": receipt.total_value, "supplier_id": receipt.supplier_id},
        )
        return 200, _receipt_public(session, receipt)

    return idempotency.execute(
        session,
        scope=POST_SCOPE,
        key=idempotency_key,
        payload=payload,
        operation=operation,
    )


def reverse_receipt(
    session: Session,
    *,
    receipt_id: uuid.UUID,
    data: ReceiptReverse,
    actor: User,
    idempotency_key: str,
) -> StoredResponse:
    payload = {"receipt_id": receipt_id, "reason": data.reason}

    def operation() -> tuple[int, StockReceiptPublic]:
        receipt = _lock_receipt(session, receipt_id)
        if receipt.reversal_of_id is not None or receipt.status != ReceiptStatus.POSTED:
            raise ReceiptNotPosted()
        payable = _payable_for(session, receipt.id, for_update=True)
        if payable is None:
            raise ReceiptNotPosted()
        if payable.paid_amount > 0:
            raise ReceiptHasPayments()
        lines = _lines_of(session, receipt.id)
        now = get_datetime_utc()
        reversal = StockReceipt(
            reference=next_receipt_reference(session, business_today(session)),
            supplier_id=receipt.supplier_id,
            receipt_date=business_today(session),
            notes=data.reason,
            status=ReceiptStatus.POSTED,
            total_value=money(-receipt.total_value),
            created_by_id=actor.id,
            posted_at=now,
            posted_by_id=actor.id,
            reversal_of_id=receipt.id,
            reversal_reason=data.reason,
        )
        session.add(reversal)
        session.flush()
        items = _items(session, [line.item_id for line in lines])
        for line in lines:
            item = items[line.item_id]
            session.add(
                _build_line(
                    reversal.id,
                    line.line_no,
                    item,
                    line.purchase_qty.copy_abs(),
                    line.purchase_unit_cost,
                    sign=-1,
                )
            )
        post_movements(
            session,
            lines=[
                MovementLine(
                    item_id=line.item_id,
                    quantity=-line.base_qty,
                    remove_at_cost=line.base_unit_cost,
                )
                for line in lines
            ],
            movement_type=MovementType.REVERSAL,
            source_type=RECEIPT_SOURCE,
            source_id=reversal.id,
            actor=actor,
            require_active=False,
        )
        receipt.status = ReceiptStatus.REVERSED
        receipt.reversed_by_id = reversal.id
        receipt.reversal_reason = data.reason
        receipt.updated_at = now
        payable.amount = Decimal("0")
        payable.paid_amount = Decimal("0")
        payable.status = PayableStatus.CANCELLED
        session.flush()
        audit.record(
            session,
            actor=actor,
            entity_type=RECEIPT_SOURCE,
            entity_id=receipt.id,
            action="reversed",
            changes={"reason": data.reason, "reversal_id": reversal.id},
        )
        return 200, _receipt_public(session, receipt)

    return idempotency.execute(
        session,
        scope=REVERSE_SCOPE,
        key=idempotency_key,
        payload=payload,
        operation=operation,
    )


def payable_public(payable: SupplierPayable) -> PayablePublic:
    return PayablePublic.model_validate(payable)
