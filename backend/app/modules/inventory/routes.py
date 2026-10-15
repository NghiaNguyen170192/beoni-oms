import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.api.deps import SessionDep
from app.models import Message, User
from app.modules.idempotency.dependencies import IdempotencyKeyDep
from app.modules.identity.dependencies import require_permission
from app.modules.identity.permissions import Permission
from app.modules.inventory import service
from app.modules.inventory.models import AdjustmentStatus, ItemType, MovementType
from app.modules.inventory.schemas import (
    InventoryCategoriesPublic,
    InventoryCategoryPublic,
    InventoryItemCreate,
    InventoryItemPublic,
    InventoryItemsPublic,
    InventoryItemUpdate,
    InventoryMovementsPublic,
    StockAdjustmentCreate,
    StockAdjustmentPublic,
    StockAdjustmentReverse,
    StockAdjustmentsPublic,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])

Viewer = Annotated[User, Depends(require_permission(Permission.INVENTORY_VIEW))]
Manager = Annotated[User, Depends(require_permission(Permission.INVENTORY_MANAGE))]
Adjuster = Annotated[User, Depends(require_permission(Permission.INVENTORY_ADJUST))]
Reverser = Annotated[User, Depends(require_permission(Permission.INVENTORY_REVERSE))]
Skip = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=500)]


@router.get("/categories", response_model=InventoryCategoriesPublic)
def read_categories(session: SessionDep, _current_user: Viewer) -> Any:
    categories = service.list_categories(session)
    return InventoryCategoriesPublic(
        data=[InventoryCategoryPublic.model_validate(c) for c in categories],
        count=len(categories),
    )


# Items


@router.get("/items", response_model=InventoryItemsPublic)
def read_items(
    session: SessionDep,
    _current_user: Viewer,
    q: Annotated[str | None, Query(max_length=100)] = None,
    category_id: uuid.UUID | None = None,
    item_type: ItemType | None = None,
    is_active: bool | None = None,
    low_stock: bool = False,
    negative_stock: bool = False,
    skip: Skip = 0,
    limit: Limit = 100,
) -> Any:
    """
    Items with current quantity, average cost, and value. Search matches SKU, name, or barcode.
    """
    items, count = service.search_items(
        session,
        q=q,
        category_id=category_id,
        item_type=item_type,
        is_active=is_active,
        low_stock=low_stock,
        negative_stock=negative_stock,
        skip=skip,
        limit=limit,
    )
    return InventoryItemsPublic(data=items, count=count)


@router.get("/low-stock", response_model=InventoryItemsPublic)
def read_low_stock(
    session: SessionDep, _current_user: Viewer, skip: Skip = 0, limit: Limit = 100
) -> Any:
    """
    Active items at or below their minimum stock threshold.
    """
    items, count = service.search_items(session, low_stock=True, skip=skip, limit=limit)
    return InventoryItemsPublic(data=items, count=count)


@router.get("/negative-stock", response_model=InventoryItemsPublic)
def read_negative_stock(
    session: SessionDep, _current_user: Viewer, skip: Skip = 0, limit: Limit = 100
) -> Any:
    """
    Items whose quantity is below zero.
    """
    items, count = service.search_items(
        session, negative_stock=True, skip=skip, limit=limit
    )
    return InventoryItemsPublic(data=items, count=count)


@router.post("/items", response_model=InventoryItemPublic, status_code=201)
def create_item(
    session: SessionDep, actor: Manager, item_in: InventoryItemCreate
) -> Any:
    """
    Create an item with zero quantity and zero average cost.
    """
    return service.create_item(session, data=item_in, actor=actor)


@router.get("/items/{item_id}", response_model=InventoryItemPublic)
def read_item(session: SessionDep, _current_user: Viewer, item_id: uuid.UUID) -> Any:
    return service.get_item_public(session, item_id)


@router.patch("/items/{item_id}", response_model=InventoryItemPublic)
def update_item(
    session: SessionDep,
    actor: Manager,
    item_id: uuid.UUID,
    item_in: InventoryItemUpdate,
) -> Any:
    """
    Edit the item definition. Quantity and cost change only through movements.
    """
    return service.update_item(session, item_id=item_id, data=item_in, actor=actor)


@router.delete("/items/{item_id}", response_model=Message)
def delete_item(session: SessionDep, actor: Manager, item_id: uuid.UUID) -> Message:
    """
    Delete an item without movements. Items with history must be deactivated.
    """
    service.delete_item(session, item_id=item_id, actor=actor)
    return Message(message="Inventory item deleted")


@router.get("/items/{item_id}/movements", response_model=InventoryMovementsPublic)
def read_item_movements(
    session: SessionDep,
    _current_user: Viewer,
    item_id: uuid.UUID,
    movement_type: MovementType | None = None,
    occurred_from: datetime | None = None,
    occurred_to: Annotated[
        datetime | None, Query(description="Exclusive upper bound")
    ] = None,
    skip: Skip = 0,
    limit: Limit = 100,
) -> Any:
    """
    Movement history, newest first. `quantity_after` is the running balance.
    """
    movements, count = service.list_movements(
        session,
        item_id=item_id,
        movement_type=movement_type,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        skip=skip,
        limit=limit,
    )
    return InventoryMovementsPublic(data=movements, count=count)


# Adjustments


@router.get("/adjustments", response_model=StockAdjustmentsPublic)
def read_adjustments(
    session: SessionDep,
    _current_user: Viewer,
    status: AdjustmentStatus | None = None,
    skip: Skip = 0,
    limit: Limit = 100,
) -> Any:
    adjustments, count = service.list_adjustments(
        session, status=status, skip=skip, limit=limit
    )
    return StockAdjustmentsPublic(data=adjustments, count=count)


@router.get("/adjustments/{adjustment_id}", response_model=StockAdjustmentPublic)
def read_adjustment(
    session: SessionDep, _current_user: Viewer, adjustment_id: uuid.UUID
) -> Any:
    return service.get_adjustment(session, adjustment_id)


@router.post("/adjustments", response_model=StockAdjustmentPublic, status_code=201)
def post_adjustment(
    session: SessionDep,
    actor: Adjuster,
    idempotency_key: IdempotencyKeyDep,
    adjustment_in: StockAdjustmentCreate,
) -> Any:
    """
    Post a reason-coded adjustment atomically. Requires an `Idempotency-Key` header;
    a repeat returns the original adjustment.
    """
    result = service.post_adjustment(
        session, data=adjustment_in, actor=actor, idempotency_key=idempotency_key
    )
    return JSONResponse(result.body, status_code=result.status_code)


@router.post(
    "/adjustments/{adjustment_id}/reverse", response_model=StockAdjustmentPublic
)
def reverse_adjustment(
    session: SessionDep,
    actor: Reverser,
    idempotency_key: IdempotencyKeyDep,
    adjustment_id: uuid.UUID,
    reverse_in: StockAdjustmentReverse,
) -> Any:
    """
    Reverse a posted adjustment with equal and opposite movements.
    """
    result = service.reverse_adjustment(
        session,
        adjustment_id=adjustment_id,
        data=reverse_in,
        actor=actor,
        idempotency_key=idempotency_key,
    )
    return JSONResponse(result.body, status_code=result.status_code)
