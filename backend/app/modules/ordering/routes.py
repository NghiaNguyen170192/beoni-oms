import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUser, SessionDep
from app.models import User
from app.modules.idempotency.dependencies import IdempotencyKeyDep
from app.modules.identity.dependencies import (
    INSUFFICIENT_PRIVILEGES,
    require_permission,
)
from app.modules.identity.permissions import Permission, has_permission
from app.modules.ordering import service
from app.modules.ordering.models import OrderType
from app.modules.ordering.schemas import (
    DiscountUpdate,
    OrderCancel,
    OrderCreate,
    OrderLinesReplace,
    OrderPublic,
    OrdersPublic,
    OrderUpdate,
    ReceiptPublic,
)
from app.modules.ordering.states import OrderStatus
from app.modules.recipes import service as recipes_service
from app.modules.recipes.schemas import (
    StockReturnCreate,
    StockReturnPublic,
    StockReturnsPublic,
)

router = APIRouter(prefix="/orders", tags=["orders"])

Creator = Annotated[User, Depends(require_permission(Permission.ORDERING_CREATE))]
Discounter = Annotated[User, Depends(require_permission(Permission.ORDERING_DISCOUNT))]
Canceller = Annotated[User, Depends(require_permission(Permission.ORDERING_CANCEL))]
Returner = Annotated[User, Depends(require_permission(Permission.INVENTORY_RETURN))]


def require_order_view(current_user: CurrentUser) -> User:
    """Own-history or full-history permission."""
    if not (
        has_permission(current_user, Permission.ORDERING_VIEW_ALL)
        or has_permission(current_user, Permission.ORDERING_VIEW_OWN)
    ):
        raise HTTPException(status_code=403, detail=INSUFFICIENT_PRIVILEGES)
    return current_user


Viewer = Annotated[User, Depends(require_order_view)]


@router.get("/", response_model=OrdersPublic)
def read_orders(
    session: SessionDep,
    current_user: Viewer,
    number: Annotated[str | None, Query(max_length=32)] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    status: OrderStatus | None = None,
    order_type: OrderType | None = None,
    cashier_id: uuid.UUID | None = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> Any:
    """
    Order history, newest first. Date bounds are inclusive business-timezone dates.
    Users with only own-history permission see only their orders.
    """
    orders, count = service.list_orders(
        session,
        actor=current_user,
        number=number,
        date_from=date_from,
        date_to=date_to,
        status=status,
        order_type=order_type,
        cashier_id=cashier_id,
        skip=skip,
        limit=limit,
    )
    return OrdersPublic(data=orders, count=count)


@router.post("/", response_model=OrderPublic, status_code=201)
def create_order(session: SessionDep, actor: Creator, order_in: OrderCreate) -> Any:
    """
    Start a draft order (optionally with lines). Totals are computed by the server.
    """
    return service.create_order(session, data=order_in, actor=actor)


@router.get("/{order_id}", response_model=OrderPublic)
def read_order(session: SessionDep, current_user: Viewer, order_id: uuid.UUID) -> Any:
    return service.get_order(session, order_id=order_id, actor=current_user)


@router.patch("/{order_id}", response_model=OrderPublic)
def update_order(
    session: SessionDep, actor: Creator, order_id: uuid.UUID, order_in: OrderUpdate
) -> Any:
    """
    Change order type, table label, or notes while the order is open.
    """
    return service.update_order(session, order_id=order_id, data=order_in, actor=actor)


@router.put("/{order_id}/lines", response_model=OrderPublic)
def replace_order_lines(
    session: SessionDep,
    actor: Creator,
    order_id: uuid.UUID,
    lines_in: OrderLinesReplace,
) -> Any:
    """
    Replace the cart in one call. Unchanged lines keep their price snapshot;
    new or changed lines snapshot the current menu item, which must be active
    and available.
    """
    return service.replace_lines(
        session, order_id=order_id, lines=lines_in.lines, actor=actor
    )


@router.put("/{order_id}/discount", response_model=OrderPublic)
def set_order_discount(
    session: SessionDep,
    actor: Discounter,
    order_id: uuid.UUID,
    discount_in: DiscountUpdate,
) -> Any:
    """
    Set or clear the order-level discount. Requires discount permission.
    """
    return service.set_order_discount(
        session, order_id=order_id, data=discount_in, actor=actor
    )


@router.put("/{order_id}/lines/{line_id}/discount", response_model=OrderPublic)
def set_line_discount(
    session: SessionDep,
    actor: Discounter,
    order_id: uuid.UUID,
    line_id: uuid.UUID,
    discount_in: DiscountUpdate,
) -> Any:
    """
    Set or clear a line discount. Requires discount permission.
    """
    return service.set_line_discount(
        session, order_id=order_id, line_id=line_id, data=discount_in, actor=actor
    )


@router.post("/{order_id}/confirm", response_model=OrderPublic)
def confirm_order(session: SessionDep, actor: Creator, order_id: uuid.UUID) -> Any:
    return service.confirm_order(session, order_id=order_id, actor=actor)


@router.post("/{order_id}/cancel", response_model=OrderPublic)
def cancel_order(
    session: SessionDep, actor: Canceller, order_id: uuid.UUID, cancel_in: OrderCancel
) -> Any:
    """
    Cancel a draft or confirmed order with a reason. Lines are kept for history.
    """
    return service.cancel_order(session, order_id=order_id, data=cancel_in, actor=actor)


@router.post("/{order_id}/complete", response_model=OrderPublic)
def complete_order(
    session: SessionDep,
    actor: Creator,
    idempotency_key: IdempotencyKeyDep,
    order_id: uuid.UUID,
) -> Any:
    """
    Complete the order. Requires an `Idempotency-Key` header; a repeat returns
    the original result.
    """
    result = service.complete_order(
        session, order_id=order_id, actor=actor, idempotency_key=idempotency_key
    )
    return JSONResponse(result.body, status_code=result.status_code)


@router.get("/{order_id}/stock-returns", response_model=StockReturnsPublic)
def read_stock_returns(
    session: SessionDep, actor: Returner, order_id: uuid.UUID
) -> Any:
    """
    Stock returns posted against a completed order.
    """
    data, count = recipes_service.list_returns(session, order_id=order_id, actor=actor)
    return StockReturnsPublic(data=data, count=count)


@router.post("/{order_id}/stock-returns", response_model=StockReturnPublic)
def create_stock_return(
    session: SessionDep,
    actor: Returner,
    idempotency_key: IdempotencyKeyDep,
    order_id: uuid.UUID,
    return_in: StockReturnCreate,
) -> Any:
    """
    Return direct-sale items to stock. Requires an `Idempotency-Key` header.
    Sellable quantities are received at the line's original unit cost.
    """
    result = recipes_service.return_to_stock(
        session,
        order_id=order_id,
        data=return_in,
        actor=actor,
        idempotency_key=idempotency_key,
    )
    return JSONResponse(result.body, status_code=result.status_code)


@router.get("/{order_id}/receipt", response_model=ReceiptPublic)
def read_receipt(session: SessionDep, current_user: Viewer, order_id: uuid.UUID) -> Any:
    """
    Printable receipt data for confirmed and later orders.
    """
    return service.get_receipt(session, order_id=order_id, actor=current_user)
