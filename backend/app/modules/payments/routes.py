import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.api.deps import SessionDep
from app.models import User
from app.modules.idempotency.dependencies import IdempotencyKeyDep
from app.modules.identity.dependencies import require_permission
from app.modules.identity.permissions import Permission
from app.modules.ordering.schemas import OrderPublic
from app.modules.payments import service
from app.modules.payments.models import PaymentStatus
from app.modules.payments.schemas import (
    OrderPaymentSummary,
    PaymentCreate,
    PaymentMethodCreate,
    PaymentMethodPublic,
    PaymentMethodsPublic,
    PaymentMethodUpdate,
    PaymentPublic,
    PaymentsPublic,
    PaymentVoid,
    RefundCreate,
    RefundPublic,
    RefundsPublic,
)

router = APIRouter(tags=["payments"])

Reader = Annotated[User, Depends(require_permission(Permission.PAYMENTS_READ))]
Recorder = Annotated[User, Depends(require_permission(Permission.PAYMENTS_RECORD))]
Voider = Annotated[User, Depends(require_permission(Permission.PAYMENTS_VOID))]
Refunder = Annotated[User, Depends(require_permission(Permission.PAYMENTS_REFUND))]
Configurer = Annotated[User, Depends(require_permission(Permission.PAYMENTS_CONFIGURE))]
Skip = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=500)]


@router.get("/payment-methods", response_model=PaymentMethodsPublic)
def read_payment_methods(
    session: SessionDep,
    _current_user: Reader,
    active_only: bool = False,
) -> Any:
    methods = service.list_methods(session, active_only=active_only)
    data = [PaymentMethodPublic.model_validate(method) for method in methods]
    return PaymentMethodsPublic(data=data, count=len(data))


@router.post("/payment-methods", response_model=PaymentMethodPublic, status_code=201)
def create_payment_method(
    session: SessionDep, actor: Configurer, method_in: PaymentMethodCreate
) -> Any:
    return service.create_method(session, data=method_in, actor=actor)


@router.patch("/payment-methods/{method_id}", response_model=PaymentMethodPublic)
def update_payment_method(
    session: SessionDep,
    actor: Configurer,
    method_id: uuid.UUID,
    method_in: PaymentMethodUpdate,
) -> Any:
    return service.update_method(
        session, method_id=method_id, data=method_in, actor=actor
    )


@router.get("/orders/{order_id}/payments", response_model=OrderPaymentSummary)
def read_order_payments(
    session: SessionDep, actor: Reader, order_id: uuid.UUID
) -> Any:
    return service.order_payments(session, order_id=order_id, actor=actor)


@router.post("/orders/{order_id}/payments", response_model=PaymentPublic)
def create_order_payment(
    session: SessionDep,
    actor: Recorder,
    idempotency_key: IdempotencyKeyDep,
    order_id: uuid.UUID,
    payment_in: PaymentCreate,
) -> Any:
    """
    Record a payment. Cash may send `tendered`; the amount is capped at the
    remaining balance and change is returned. Requires `Idempotency-Key`.
    """
    result = service.record_payment(
        session,
        order_id=order_id,
        data=payment_in,
        actor=actor,
        idempotency_key=idempotency_key,
    )
    return JSONResponse(result.body, status_code=result.status_code)


@router.post("/orders/{order_id}/pay-and-complete", response_model=OrderPublic)
def pay_and_complete_order(
    session: SessionDep,
    actor: Recorder,
    idempotency_key: IdempotencyKeyDep,
    order_id: uuid.UUID,
    payment_in: PaymentCreate,
) -> Any:
    """
    Record the payment and complete the order in one transaction.
    """
    result = service.pay_and_complete(
        session,
        order_id=order_id,
        data=payment_in,
        actor=actor,
        idempotency_key=idempotency_key,
    )
    return JSONResponse(result.body, status_code=result.status_code)


@router.post("/payments/{payment_id}/void", response_model=PaymentPublic)
def void_payment(
    session: SessionDep,
    actor: Voider,
    idempotency_key: IdempotencyKeyDep,
    payment_id: uuid.UUID,
    void_in: PaymentVoid,
) -> Any:
    """
    Void a payment on an order that is not completed. Completed orders are refunded.
    """
    result = service.void_payment(
        session,
        payment_id=payment_id,
        data=void_in,
        actor=actor,
        idempotency_key=idempotency_key,
    )
    return JSONResponse(result.body, status_code=result.status_code)


@router.get("/payments", response_model=PaymentsPublic)
def read_payments(
    session: SessionDep,
    actor: Reader,
    date_from: date | None = None,
    date_to: date | None = None,
    method_id: uuid.UUID | None = None,
    status: PaymentStatus | None = None,
    cashier_id: uuid.UUID | None = None,
    order_id: uuid.UUID | None = None,
    skip: Skip = 0,
    limit: Limit = 100,
) -> Any:
    """
    Payments visible to the caller. Totals are active payments minus refunds per method.
    """
    return service.list_payments(
        session,
        actor=actor,
        date_from=date_from,
        date_to=date_to,
        method_id=method_id,
        status=status,
        cashier_id=cashier_id,
        order_id=order_id,
        skip=skip,
        limit=limit,
    )


@router.post("/orders/{order_id}/refunds", response_model=RefundPublic)
def create_order_refund(
    session: SessionDep,
    actor: Refunder,
    idempotency_key: IdempotencyKeyDep,
    order_id: uuid.UUID,
    refund_in: RefundCreate,
) -> Any:
    """
    Record a refund against amounts paid. Does not change inventory.
    """
    result = service.record_refund(
        session,
        order_id=order_id,
        data=refund_in,
        actor=actor,
        idempotency_key=idempotency_key,
    )
    return JSONResponse(result.body, status_code=result.status_code)


@router.get("/refunds", response_model=RefundsPublic)
def read_refunds(
    session: SessionDep,
    actor: Reader,
    date_from: date | None = None,
    date_to: date | None = None,
    method_id: uuid.UUID | None = None,
    cashier_id: uuid.UUID | None = None,
    order_id: uuid.UUID | None = None,
    skip: Skip = 0,
    limit: Limit = 100,
) -> Any:
    return service.list_refunds(
        session,
        actor=actor,
        date_from=date_from,
        date_to=date_to,
        method_id=method_id,
        cashier_id=cashier_id,
        order_id=order_id,
        skip=skip,
        limit=limit,
    )
