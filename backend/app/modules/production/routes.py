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
from app.modules.production import service
from app.modules.production.models import ProductionBatchStatus
from app.modules.production.schemas import (
    ProductionBatchComplete,
    ProductionBatchCreate,
    ProductionBatchesPublic,
    ProductionBatchPublic,
    ProductionBatchReverse,
    ProductionBatchTraceabilityPublic,
    ProductionBatchUpdate,
    FinishedGoodsAvailabilityPublic,
)

router = APIRouter(prefix="/production/batches", tags=["production"])

Reader = Annotated[User, Depends(require_permission(Permission.PRODUCTION_VIEW))]
Manager = Annotated[User, Depends(require_permission(Permission.PRODUCTION_MANAGE))]
Completer = Annotated[
    User, Depends(require_permission(Permission.PRODUCTION_COMPLETE))
]
Reverser = Annotated[User, Depends(require_permission(Permission.PRODUCTION_REVERSE))]
TraceabilityReader = Annotated[
    User, Depends(require_permission(Permission.PRODUCTION_TRACEABILITY))
]
PosAvailabilityReader = Annotated[
    User, Depends(require_permission(Permission.ORDERING_CREATE))
]
Skip = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=500)]


@router.get("", response_model=ProductionBatchesPublic)
def read_batches(
    session: SessionDep,
    _current_user: Reader,
    status: ProductionBatchStatus | None = None,
    planned_from: date | None = None,
    planned_to: date | None = None,
    recipe_id: uuid.UUID | None = None,
    menu_item_id: uuid.UUID | None = None,
    skip: Skip = 0,
    limit: Limit = 100,
) -> Any:
    data, count = service.list_batches(
        session,
        status=status,
        planned_from=planned_from,
        planned_to=planned_to,
        recipe_id=recipe_id,
        menu_item_id=menu_item_id,
        skip=skip,
        limit=limit,
    )
    return ProductionBatchesPublic(data=data, count=count)


@router.get("/availability", response_model=FinishedGoodsAvailabilityPublic)
def read_finished_good_availability(
    session: SessionDep, _current_user: PosAvailabilityReader
) -> Any:
    return service.list_finished_good_availability(session)


@router.post("", response_model=ProductionBatchPublic, status_code=201)
def create_batch(
    session: SessionDep, actor: Manager, batch_in: ProductionBatchCreate
) -> Any:
    return service.create_batch(session, data=batch_in, actor=actor)


@router.get("/{batch_id}", response_model=ProductionBatchPublic)
def read_batch(
    session: SessionDep, _current_user: Reader, batch_id: uuid.UUID
) -> Any:
    return service.get_batch(session, batch_id)


@router.get(
    "/{batch_id}/traceability",
    response_model=ProductionBatchTraceabilityPublic,
)
def read_batch_traceability(
    session: SessionDep, _current_user: TraceabilityReader, batch_id: uuid.UUID
) -> Any:
    return service.get_batch_traceability(session, batch_id)


@router.patch("/{batch_id}", response_model=ProductionBatchPublic)
def update_batch(
    session: SessionDep,
    actor: Manager,
    batch_id: uuid.UUID,
    batch_in: ProductionBatchUpdate,
) -> Any:
    return service.update_batch(
        session, batch_id=batch_id, data=batch_in, actor=actor
    )


@router.post("/{batch_id}/complete", response_model=ProductionBatchPublic)
def complete_batch(
    session: SessionDep,
    actor: Completer,
    idempotency_key: IdempotencyKeyDep,
    batch_id: uuid.UUID,
    batch_in: ProductionBatchComplete,
) -> Any:
    result = service.complete_batch(
        session,
        batch_id=batch_id,
        data=batch_in,
        actor=actor,
        idempotency_key=idempotency_key,
    )
    return JSONResponse(result.body, status_code=result.status_code)


@router.post("/{batch_id}/reverse", response_model=ProductionBatchPublic)
def reverse_batch(
    session: SessionDep,
    actor: Reverser,
    idempotency_key: IdempotencyKeyDep,
    batch_id: uuid.UUID,
    batch_in: ProductionBatchReverse,
) -> Any:
    result = service.reverse_batch(
        session,
        batch_id=batch_id,
        data=batch_in,
        actor=actor,
        idempotency_key=idempotency_key,
    )
    return JSONResponse(result.body, status_code=result.status_code)
