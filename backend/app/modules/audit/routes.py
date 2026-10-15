import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.api.deps import SessionDep
from app.modules.audit import service
from app.modules.audit.schemas import AuditLogPublic, AuditLogsPublic
from app.modules.identity.dependencies import require_permission
from app.modules.identity.permissions import Permission

router = APIRouter(prefix="/audit-log", tags=["audit"])


@router.get(
    "/",
    dependencies=[Depends(require_permission(Permission.AUDIT_READ))],
    response_model=AuditLogsPublic,
)
def read_audit_log(
    session: SessionDep,
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor_id: uuid.UUID | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> AuditLogsPublic:
    """
    List audit entries, newest first. `occurred_to` is exclusive.
    """
    rows, count = service.list_entries(
        session,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        skip=skip,
        limit=limit,
    )
    data = [
        AuditLogPublic.model_validate(
            entry, update={"actor_email": email, "actor_name": name}
        )
        for entry, email, name in rows
    ]
    return AuditLogsPublic(data=data, count=count)
