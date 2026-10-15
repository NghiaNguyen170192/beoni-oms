import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from app.core.errors import Invalid, violated_constraint
from app.core.money import money
from app.models import User, get_datetime_utc
from app.modules.audit import service as audit
from app.modules.idempotency import service as idempotency
from app.modules.idempotency.service import StoredResponse
from app.modules.identity.permissions import Permission, has_permission
from app.modules.ordering.models import Order, OrderLine
from app.modules.ordering.states import OrderStatus, assert_transition
from app.modules.payments.errors import (
    Overpayment,
    OverRefund,
    PaymentAlreadyVoided,
    PaymentMethodInactive,
    PaymentMethodNameTaken,
    PaymentMethodNotFound,
    PaymentNotAllowed,
    PaymentNotFound,
    PaymentShort,
    RefundNotAllowed,
    VoidNotAllowed,
)
from app.modules.payments.models import (
    METHOD_NAME_INDEX,
    Payment,
    PaymentMethod,
    PaymentMethodKind,
    PaymentStatus,
    Refund,
    RefundLine,
)
from app.modules.payments.schemas import (
    MethodTotal,
    OrderPaymentSummary,
    PaymentCreate,
    PaymentMethodCreate,
    PaymentMethodPublic,
    PaymentMethodUpdate,
    PaymentPublic,
    PaymentsPublic,
    PaymentVoid,
    RefundCreate,
    RefundPublic,
    RefundsPublic,
)
from app.modules.settings.service import get_settings

RECORD_SCOPE = "payment.record"
VOID_SCOPE = "payment.void"
PAY_COMPLETE_SCOPE = "order.pay_complete"
REFUND_SCOPE = "payment.refund"
PAYABLE_STATUSES = frozenset(
    {OrderStatus.DRAFT, OrderStatus.CONFIRMED, OrderStatus.PAID}
)
FINISHED_STATUSES = frozenset(
    {OrderStatus.COMPLETED, OrderStatus.PARTIALLY_REFUNDED, OrderStatus.REFUNDED}
)
REFUNDABLE_STATUSES = frozenset(
    {OrderStatus.COMPLETED, OrderStatus.PARTIALLY_REFUNDED}
)


def _dec(value: object) -> Decimal:
    return money(Decimal(str(value)))


def active_paid(session: Session, order_id: uuid.UUID) -> Decimal:
    total = session.exec(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.order_id == order_id, Payment.status == PaymentStatus.ACTIVE
        )
    ).one()
    return _dec(total)


def refunded_total(session: Session, order_id: uuid.UUID) -> Decimal:
    total = session.exec(
        select(func.coalesce(func.sum(Refund.amount), 0)).where(
            Refund.order_id == order_id
        )
    ).one()
    return _dec(total)


def ensure_paid(
    session: Session, order: Order, _lines: list[OrderLine], _actor: User
) -> None:
    """Completion step: active payments must cover the order total."""
    paid = active_paid(session, order.id)
    if paid < order.total:
        remaining = money(order.total - paid)
        raise PaymentShort(f"Remaining amount is {remaining}")


def _method(session: Session, method_id: uuid.UUID, *, active: bool) -> PaymentMethod:
    method = session.get(PaymentMethod, method_id)
    if method is None:
        raise PaymentMethodNotFound()
    if active and not method.is_active:
        raise PaymentMethodInactive()
    return method


def _sync_paid_status(session: Session, order: Order) -> None:
    paid = active_paid(session, order.id)
    covered = paid >= order.total
    if order.status in {OrderStatus.DRAFT, OrderStatus.CONFIRMED} and covered:
        assert_transition(order.status, OrderStatus.PAID, via_payment=True)
        order.status = OrderStatus.PAID
        order.updated_at = get_datetime_utc()
    elif order.status == OrderStatus.PAID and not covered:
        assert_transition(order.status, OrderStatus.CONFIRMED, via_payment=True)
        order.status = OrderStatus.CONFIRMED
        if order.confirmed_at is None:
            order.confirmed_at = get_datetime_utc()
        order.updated_at = get_datetime_utc()


def _payment_public(
    payment: Payment, order: Order, method: PaymentMethod
) -> PaymentPublic:
    return PaymentPublic(
        id=payment.id,
        order_id=payment.order_id,
        order_number=order.number,
        method_id=method.id,
        method_name=method.name,
        method_kind=method.kind,
        amount=payment.amount,
        tendered=payment.tendered,
        change_amount=payment.change_amount,
        reference=payment.reference,
        status=payment.status,
        void_reason=payment.void_reason,
        recorded_by_id=payment.recorded_by_id,
        recorded_at=payment.recorded_at,
        voided_at=payment.voided_at,
    )


def _load_payment_public(session: Session, payment: Payment) -> PaymentPublic:
    order = session.get(Order, payment.order_id)
    method = session.get(PaymentMethod, payment.method_id)
    assert order is not None and method is not None
    return _payment_public(payment, order, method)


def apply_payment(
    session: Session, *, order: Order, data: PaymentCreate, actor: User
) -> Payment:
    """Stage one payment on a locked order. Does not commit."""
    if order.status not in PAYABLE_STATUSES:
        raise PaymentNotAllowed()
    method = _method(session, data.method_id, active=True)
    remaining = money(order.total - active_paid(session, order.id))
    if remaining <= 0:
        raise Overpayment()
    if method.kind == PaymentMethodKind.CASH and data.tendered is not None:
        tendered = money(data.tendered)
        amount = tendered if tendered <= remaining else remaining
        change = money(tendered - amount)
    else:
        if data.amount is None:
            raise Invalid("Payment amount is required")
        amount = money(data.amount)
        if amount > remaining:
            raise Overpayment()
        tendered = amount if method.kind == PaymentMethodKind.CASH else None
        change = Decimal("0.00") if method.kind == PaymentMethodKind.CASH else None
    if amount <= 0:
        raise Overpayment()
    payment = Payment(
        order_id=order.id,
        method_id=method.id,
        amount=amount,
        tendered=tendered,
        change_amount=change,
        reference=data.reference,
        recorded_by_id=actor.id,
    )
    session.add(payment)
    session.flush()
    from app.modules.accounting.ledger import record_money_movement

    record_money_movement(
        session,
        account_id=method.account_id,
        amount=amount,
        occurred_at=payment.recorded_at,
        source_type="payment",
        source_id=payment.id,
        actor_id=actor.id,
    )
    _sync_paid_status(session, order)
    audit.record(
        session,
        actor=actor,
        entity_type="payment",
        entity_id=payment.id,
        action="recorded",
        changes={"order_id": order.id, "amount": amount, "method_id": method.id},
    )
    return payment


def record_payment(
    session: Session,
    *,
    order_id: uuid.UUID,
    data: PaymentCreate,
    actor: User,
    idempotency_key: str,
) -> StoredResponse:
    from app.modules.ordering.service import _load

    def operation() -> tuple[int, PaymentPublic]:
        order = _load(session, order_id, actor, for_update=True)
        payment = apply_payment(session, order=order, data=data, actor=actor)
        return 201, _load_payment_public(session, payment)

    return idempotency.execute(
        session,
        scope=RECORD_SCOPE,
        key=idempotency_key,
        payload={"order_id": str(order_id), **data.model_dump(mode="json")},
        operation=operation,
    )


def void_payment(
    session: Session,
    *,
    payment_id: uuid.UUID,
    data: PaymentVoid,
    actor: User,
    idempotency_key: str,
) -> StoredResponse:
    from app.modules.ordering.service import _load

    def operation() -> tuple[int, PaymentPublic]:
        payment = session.get(Payment, payment_id)
        if payment is None:
            raise PaymentNotFound()
        order = _load(session, payment.order_id, actor, for_update=True)
        session.refresh(payment)
        if order.status in FINISHED_STATUSES:
            raise VoidNotAllowed()
        if payment.status == PaymentStatus.VOIDED:
            raise PaymentAlreadyVoided()
        now = get_datetime_utc()
        payment.status = PaymentStatus.VOIDED
        payment.void_reason = data.reason
        payment.voided_at = now
        payment.voided_by_id = actor.id
        session.add(payment)
        session.flush()
        from app.modules.accounting.ledger import record_money_movement

        method = _method(session, payment.method_id, active=False)
        record_money_movement(
            session,
            account_id=method.account_id,
            amount=money(-payment.amount),
            occurred_at=now,
            source_type="payment_void",
            source_id=payment.id,
            actor_id=actor.id,
            note=data.reason,
        )
        _sync_paid_status(session, order)
        audit.record(
            session,
            actor=actor,
            entity_type="payment",
            entity_id=payment.id,
            action="voided",
            changes={"reason": data.reason},
        )
        return 200, _payment_public(
            payment, order, _method(session, payment.method_id, active=False)
        )

    return idempotency.execute(
        session,
        scope=VOID_SCOPE,
        key=idempotency_key,
        payload={"payment_id": str(payment_id), "reason": data.reason},
        operation=operation,
    )


def pay_and_complete(
    session: Session,
    *,
    order_id: uuid.UUID,
    data: PaymentCreate,
    actor: User,
    idempotency_key: str,
) -> StoredResponse:
    from app.modules.ordering.service import _load, apply_completion, to_public

    def operation() -> tuple[int, object]:
        order = _load(session, order_id, actor, for_update=True)
        apply_payment(session, order=order, data=data, actor=actor)
        apply_completion(session, order, actor)
        return 200, to_public(session, order)

    return idempotency.execute(
        session,
        scope=PAY_COMPLETE_SCOPE,
        key=idempotency_key,
        payload={"order_id": str(order_id), **data.model_dump(mode="json")},
        operation=operation,
    )


def _refund_public(session: Session, refund: Refund) -> RefundPublic:
    order = session.get(Order, refund.order_id)
    method = session.get(PaymentMethod, refund.method_id)
    assert order is not None and method is not None
    lines = session.exec(
        select(RefundLine).where(RefundLine.refund_id == refund.id)
    ).all()
    return RefundPublic(
        id=refund.id,
        order_id=refund.order_id,
        order_number=order.number,
        method_id=method.id,
        method_name=method.name,
        method_kind=method.kind,
        amount=refund.amount,
        reason=refund.reason,
        reference=refund.reference,
        recorded_by_id=refund.recorded_by_id,
        recorded_at=refund.recorded_at,
        lines=list(lines),
    )


def record_refund(
    session: Session,
    *,
    order_id: uuid.UUID,
    data: RefundCreate,
    actor: User,
    idempotency_key: str,
) -> StoredResponse:
    from app.modules.ordering.service import _lines, _load

    def operation() -> tuple[int, RefundPublic]:
        order = _load(session, order_id, actor, for_update=True)
        if order.status not in REFUNDABLE_STATUSES:
            raise RefundNotAllowed()
        method = _method(session, data.method_id, active=True)
        amount = money(data.amount)
        if data.lines:
            line_sum = money(sum((line.amount for line in data.lines), Decimal("0")))
            if line_sum != amount:
                raise Invalid("Refund line amounts must add up to the refund amount")
            known = {line.id for line in _lines(session, order.id)}
            if any(line.order_line_id not in known for line in data.lines):
                raise Invalid("Refund line does not belong to this order")
        already = refunded_total(session, order.id)
        if already + amount > active_paid(session, order.id):
            raise OverRefund()
        refund = Refund(
            order_id=order.id,
            method_id=method.id,
            amount=amount,
            reason=data.reason,
            reference=data.reference,
            recorded_by_id=actor.id,
        )
        session.add(refund)
        session.flush()
        from app.modules.accounting.ledger import record_money_movement

        record_money_movement(
            session,
            account_id=method.account_id,
            amount=money(-amount),
            occurred_at=refund.recorded_at,
            source_type="refund",
            source_id=refund.id,
            actor_id=actor.id,
        )
        for line in data.lines:
            session.add(
                RefundLine(
                    refund_id=refund.id,
                    order_line_id=line.order_line_id,
                    quantity=line.quantity,
                    amount=money(line.amount),
                )
            )
        target = (
            OrderStatus.REFUNDED
            if already + amount >= active_paid(session, order.id)
            else OrderStatus.PARTIALLY_REFUNDED
        )
        assert_transition(order.status, target, via_payment=True)
        order.status = target
        order.updated_at = get_datetime_utc()
        audit.record(
            session,
            actor=actor,
            entity_type="refund",
            entity_id=refund.id,
            action="recorded",
            changes={"order_id": order.id, "amount": amount},
        )
        return 201, _refund_public(session, refund)

    return idempotency.execute(
        session,
        scope=REFUND_SCOPE,
        key=idempotency_key,
        payload={"order_id": str(order_id), **data.model_dump(mode="json")},
        operation=operation,
    )


def order_payments(
    session: Session, *, order_id: uuid.UUID, actor: User
) -> OrderPaymentSummary:
    from app.modules.ordering.service import _load

    order = _load(session, order_id, actor)
    rows = session.exec(
        select(Payment, PaymentMethod)
        .join(PaymentMethod, col(PaymentMethod.id) == col(Payment.method_id))
        .where(Payment.order_id == order.id)
        .order_by(col(Payment.recorded_at))
    ).all()
    paid = active_paid(session, order.id)
    return OrderPaymentSummary(
        order_id=order.id,
        order_total=order.total,
        paid_amount=paid,
        refunded_amount=refunded_total(session, order.id),
        remaining=money(order.total - paid),
        payments=[_payment_public(payment, order, method) for payment, method in rows],
    )


def _bounds(
    session: Session, date_from: date | None, date_to: date | None
) -> tuple[datetime | None, datetime | None]:
    zone = ZoneInfo(get_settings(session).timezone)
    start = (
        datetime.combine(date_from, time.min, tzinfo=zone) if date_from else None
    )
    end = (
        datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=zone)
        if date_to
        else None
    )
    return start, end


def _own_only(actor: User) -> bool:
    return not has_permission(actor, Permission.ORDERING_VIEW_ALL)


def list_payments(
    session: Session,
    *,
    actor: User,
    date_from: date | None = None,
    date_to: date | None = None,
    method_id: uuid.UUID | None = None,
    status: PaymentStatus | None = None,
    cashier_id: uuid.UUID | None = None,
    order_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 100,
) -> PaymentsPublic:
    start, end = _bounds(session, date_from, date_to)
    conditions = []
    if _own_only(actor):
        conditions.append(col(Payment.recorded_by_id) == actor.id)
    elif cashier_id is not None:
        conditions.append(col(Payment.recorded_by_id) == cashier_id)
    if method_id is not None:
        conditions.append(col(Payment.method_id) == method_id)
    if status is not None:
        conditions.append(col(Payment.status) == status)
    if order_id is not None:
        conditions.append(col(Payment.order_id) == order_id)
    if start is not None:
        conditions.append(col(Payment.recorded_at) >= start)
    if end is not None:
        conditions.append(col(Payment.recorded_at) < end)
    query = (
        select(Payment, PaymentMethod, Order)
        .join(PaymentMethod, col(PaymentMethod.id) == col(Payment.method_id))
        .join(Order, col(Order.id) == col(Payment.order_id))
        .order_by(col(Payment.recorded_at).desc())
    )
    if conditions:
        query = query.where(*conditions)
    rows = session.exec(query).all()
    data = [_payment_public(payment, order, method) for payment, method, order in rows]
    totals = _method_nets(session, start, end, actor)
    if method_id is not None:
        totals = [row for row in totals if row.method_id == method_id]
    return PaymentsPublic(data=data[skip : skip + limit], count=len(data), totals=totals)


def list_refunds(
    session: Session,
    *,
    actor: User,
    date_from: date | None = None,
    date_to: date | None = None,
    method_id: uuid.UUID | None = None,
    cashier_id: uuid.UUID | None = None,
    order_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 100,
) -> RefundsPublic:
    start, end = _bounds(session, date_from, date_to)
    conditions = []
    if _own_only(actor):
        conditions.append(col(Refund.recorded_by_id) == actor.id)
    elif cashier_id is not None:
        conditions.append(col(Refund.recorded_by_id) == cashier_id)
    if method_id is not None:
        conditions.append(col(Refund.method_id) == method_id)
    if order_id is not None:
        conditions.append(col(Refund.order_id) == order_id)
    if start is not None:
        conditions.append(col(Refund.recorded_at) >= start)
    if end is not None:
        conditions.append(col(Refund.recorded_at) < end)
    query = select(Refund).order_by(col(Refund.recorded_at).desc())
    if conditions:
        query = query.where(*conditions)
    rows = session.exec(query).all()
    data = [_refund_public(session, refund) for refund in rows]
    totals = _method_nets(session, start, end, actor)
    if method_id is not None:
        totals = [row for row in totals if row.method_id == method_id]
    return RefundsPublic(data=data[skip : skip + limit], count=len(data), totals=totals)


def _method_nets(
    session: Session, start: datetime | None, end: datetime | None, actor: User
) -> list[MethodTotal]:
    """Active payments minus refunds, per method, inside the same window."""
    pay_filters = [Payment.status == PaymentStatus.ACTIVE]
    refund_filters: list[object] = []
    if _own_only(actor):
        pay_filters.append(col(Payment.recorded_by_id) == actor.id)
        refund_filters.append(col(Refund.recorded_by_id) == actor.id)
    if start is not None:
        pay_filters.append(col(Payment.recorded_at) >= start)
        refund_filters.append(col(Refund.recorded_at) >= start)
    if end is not None:
        pay_filters.append(col(Payment.recorded_at) < end)
        refund_filters.append(col(Refund.recorded_at) < end)
    paid_rows = session.exec(
        select(Payment.method_id, func.coalesce(func.sum(Payment.amount), 0))
        .where(*pay_filters)
        .group_by(col(Payment.method_id))
    ).all()
    refund_query = select(
        Refund.method_id, func.coalesce(func.sum(Refund.amount), 0)
    ).group_by(col(Refund.method_id))
    if refund_filters:
        refund_query = refund_query.where(*refund_filters)
    refund_rows = session.exec(refund_query).all()
    paid = {method_id: _dec(total) for method_id, total in paid_rows}
    refunded = {method_id: _dec(total) for method_id, total in refund_rows}
    methods = {
        method.id: method
        for method in session.exec(select(PaymentMethod)).all()
    }
    totals = []
    for method_id in sorted(paid.keys() | refunded.keys(), key=lambda item: str(item)):
        method = methods[method_id]
        totals.append(
            MethodTotal(
                method_id=method.id,
                method_name=method.name,
                method_kind=method.kind,
                total=money(
                    paid.get(method_id, Decimal("0.00"))
                    - refunded.get(method_id, Decimal("0.00"))
                ),
            )
        )
    return totals


# Methods


def list_methods(
    session: Session, *, active_only: bool = False
) -> list[PaymentMethod]:
    query = select(PaymentMethod).order_by(col(PaymentMethod.name))
    if active_only:
        query = query.where(PaymentMethod.is_active == True)  # noqa: E712
    return list(session.exec(query).all())


def create_method(
    session: Session, *, data: PaymentMethodCreate, actor: User
) -> PaymentMethodPublic:
    from app.modules.accounting.ledger import default_account

    account = default_account(session, data.kind)
    method = PaymentMethod(
        name=data.name,
        kind=data.kind,
        is_active=data.is_active,
        account_id=account.id,
    )
    session.add(method)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        if violated_constraint(exc) == METHOD_NAME_INDEX:
            raise PaymentMethodNameTaken() from exc
        raise
    audit.record(
        session,
        actor=actor,
        entity_type="payment_method",
        entity_id=method.id,
        action="created",
        changes={"name": method.name, "kind": method.kind},
    )
    session.commit()
    session.refresh(method)
    return PaymentMethodPublic.model_validate(method)


def update_method(
    session: Session, *, method_id: uuid.UUID, data: PaymentMethodUpdate, actor: User
) -> PaymentMethodPublic:
    method = session.get(PaymentMethod, method_id)
    if method is None:
        raise PaymentMethodNotFound()
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes and not changes["name"]:
        raise Invalid("Name must not be blank")
    for field, value in changes.items():
        setattr(method, field, value)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        if violated_constraint(exc) == METHOD_NAME_INDEX:
            raise PaymentMethodNameTaken() from exc
        raise
    audit.record(
        session,
        actor=actor,
        entity_type="payment_method",
        entity_id=method.id,
        action="updated",
        changes=changes,
    )
    session.commit()
    session.refresh(method)
    return PaymentMethodPublic.model_validate(method)
