import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import JSONResponse

from app.api.deps import SessionDep
from app.models import Message, User
from app.modules.idempotency.dependencies import IdempotencyKeyDep
from app.modules.identity.dependencies import require_permission
from app.modules.identity.permissions import Permission
from app.modules.purchasing import service
from app.modules.purchasing.models import ReceiptStatus
from app.modules.purchasing.schemas import (
    ReceiptCreate,
    ReceiptPost,
    ReceiptReverse,
    ReceiptsPublic,
    ReceiptUpdate,
    StockReceiptPublic,
    SupplierBalance,
    SupplierCreate,
    SupplierPublic,
    SuppliersPublic,
    SupplierUpdate,
)

router = APIRouter(prefix="/purchasing", tags=["purchasing"])

Reader = Annotated[User, Depends(require_permission(Permission.PURCHASING_READ))]
Manager = Annotated[User, Depends(require_permission(Permission.PURCHASING_MANAGE))]
Poster = Annotated[User, Depends(require_permission(Permission.PURCHASING_POST))]
Reverser = Annotated[User, Depends(require_permission(Permission.PURCHASING_REVERSE))]
Skip = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=500)]


@router.get("/suppliers", response_model=SuppliersPublic)
def read_suppliers(
    session: SessionDep,
    _current_user: Reader,
    q: Annotated[str | None, Query(max_length=100)] = None,
    is_active: bool | None = None,
    skip: Skip = 0,
    limit: Limit = 100,
) -> Any:
    data, count = service.list_suppliers(
        session, q=q, is_active=is_active, skip=skip, limit=limit
    )
    return SuppliersPublic(data=data, count=count)


@router.post("/suppliers", response_model=SupplierPublic, status_code=201)
def create_supplier(
    session: SessionDep, actor: Manager, supplier_in: SupplierCreate
) -> Any:
    return service.create_supplier(session, data=supplier_in, actor=actor)


@router.get("/suppliers/{supplier_id}", response_model=SupplierPublic)
def read_supplier(
    session: SessionDep, _current_user: Reader, supplier_id: uuid.UUID
) -> Any:
    return service.get_supplier(session, supplier_id)


@router.patch("/suppliers/{supplier_id}", response_model=SupplierPublic)
def update_supplier(
    session: SessionDep,
    actor: Manager,
    supplier_id: uuid.UUID,
    supplier_in: SupplierUpdate,
) -> Any:
    return service.update_supplier(
        session, supplier_id=supplier_id, data=supplier_in, actor=actor
    )


@router.delete("/suppliers/{supplier_id}", response_model=Message)
def delete_supplier(
    session: SessionDep, actor: Manager, supplier_id: uuid.UUID
) -> Message:
    service.delete_supplier(session, supplier_id=supplier_id, actor=actor)
    return Message(message="Supplier deleted")


@router.get("/suppliers/{supplier_id}/balance", response_model=SupplierBalance)
def read_supplier_balance(
    session: SessionDep, _current_user: Reader, supplier_id: uuid.UUID
) -> Any:
    return service.supplier_balance(session, supplier_id)


@router.get("/suppliers/{supplier_id}/receipts", response_model=ReceiptsPublic)
def read_supplier_receipts(
    session: SessionDep,
    _current_user: Reader,
    supplier_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
    skip: Skip = 0,
    limit: Limit = 100,
) -> Any:
    data, count = service.supplier_history(
        session,
        supplier_id,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return ReceiptsPublic(data=data, count=count)


@router.get("/receipts", response_model=ReceiptsPublic)
def read_receipts(
    session: SessionDep,
    _current_user: Reader,
    supplier_id: uuid.UUID | None = None,
    status: ReceiptStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: Annotated[str | None, Query(max_length=64)] = None,
    skip: Skip = 0,
    limit: Limit = 100,
) -> Any:
    data, count = service.list_receipts(
        session,
        supplier_id=supplier_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        q=q,
        skip=skip,
        limit=limit,
    )
    return ReceiptsPublic(data=data, count=count)


@router.post("/receipts", response_model=StockReceiptPublic, status_code=201)
def create_receipt(
    session: SessionDep, actor: Manager, receipt_in: ReceiptCreate
) -> Any:
    return service.create_receipt(session, data=receipt_in, actor=actor)


@router.get("/receipts/{receipt_id}", response_model=StockReceiptPublic)
def read_receipt(
    session: SessionDep, _current_user: Reader, receipt_id: uuid.UUID
) -> Any:
    return service.get_receipt(session, receipt_id)


@router.patch("/receipts/{receipt_id}", response_model=StockReceiptPublic)
def update_receipt(
    session: SessionDep,
    actor: Manager,
    receipt_id: uuid.UUID,
    receipt_in: ReceiptUpdate,
) -> Any:
    return service.update_receipt(
        session, receipt_id=receipt_id, data=receipt_in, actor=actor
    )


@router.delete("/receipts/{receipt_id}", response_model=Message)
def delete_receipt(
    session: SessionDep, actor: Manager, receipt_id: uuid.UUID
) -> Message:
    """
    Delete a draft receipt. Posted receipts are reversed, never deleted.
    """
    service.delete_receipt(session, receipt_id=receipt_id, actor=actor)
    return Message(message="Stock receipt deleted")


@router.post("/receipts/{receipt_id}/post", response_model=StockReceiptPublic)
def post_receipt(
    session: SessionDep,
    actor: Poster,
    idempotency_key: IdempotencyKeyDep,
    receipt_id: uuid.UUID,
    body: ReceiptPost | None = Body(default=None),
) -> Any:
    """
    Post a draft receipt: stock, valuation, and supplier payable change together.
    Requires an `Idempotency-Key` header.
    """
    result = service.post_receipt(
        session,
        receipt_id=receipt_id,
        actor=actor,
        idempotency_key=idempotency_key,
        payment_amount=body.payment_amount if body else None,
        account_id=body.account_id if body else None,
    )
    return JSONResponse(result.body, status_code=result.status_code)


@router.post("/receipts/{receipt_id}/reverse", response_model=StockReceiptPublic)
def reverse_receipt(
    session: SessionDep,
    actor: Reverser,
    idempotency_key: IdempotencyKeyDep,
    receipt_id: uuid.UUID,
    reverse_in: ReceiptReverse,
) -> Any:
    """
    Reverse a posted unpaid receipt with opposite movements at the original cost.
    """
    result = service.reverse_receipt(
        session,
        receipt_id=receipt_id,
        data=reverse_in,
        actor=actor,
        idempotency_key=idempotency_key,
    )
    return JSONResponse(result.body, status_code=result.status_code)
