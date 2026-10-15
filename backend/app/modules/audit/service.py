import uuid
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from pydantic_core import to_jsonable_python
from sqlmodel import Session, col, func, select

from app.core.logging import request_id_var
from app.models import User
from app.modules.audit.models import AuditLog


def to_json_value(value: Any) -> Any:
    """JSON-safe value for `changes`; Decimal becomes a string, never a float."""
    return to_jsonable_python(value)


def diff(
    old: Mapping[str, Any], new: Mapping[str, Any], fields: Iterable[str]
) -> dict[str, Any]:
    """`{field: {"old": ..., "new": ...}}` for each field whose value changed."""
    changes: dict[str, Any] = {}
    for field in fields:
        old_value = to_json_value(old.get(field))
        new_value = to_json_value(new.get(field))
        if old_value != new_value:
            changes[field] = {"old": old_value, "new": new_value}
    return changes


def record(
    session: Session,
    *,
    actor: User | None,
    entity_type: str,
    entity_id: Any,
    action: str,
    changes: Mapping[str, Any] | None = None,
) -> AuditLog:
    """Stage an audit entry in the caller's transaction. Never commits."""
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        changes=to_json_value(dict(changes)) if changes is not None else None,
        request_id=request_id_var.get(),
    )
    session.add(entry)
    return entry


def list_entries(
    session: Session,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor_id: uuid.UUID | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[tuple[AuditLog, str | None, str | None]], int]:
    """Entries with the actor's email and full name, newest first."""
    conditions = []
    if entity_type is not None:
        conditions.append(col(AuditLog.entity_type) == entity_type)
    if entity_id is not None:
        conditions.append(col(AuditLog.entity_id) == entity_id)
    if actor_id is not None:
        conditions.append(col(AuditLog.actor_id) == actor_id)
    if occurred_from is not None:
        conditions.append(col(AuditLog.occurred_at) >= occurred_from)
    if occurred_to is not None:
        conditions.append(col(AuditLog.occurred_at) < occurred_to)

    count = session.exec(
        select(func.count()).select_from(AuditLog).where(*conditions)
    ).one()
    rows = session.exec(
        select(AuditLog, User.email, User.full_name)
        .outerjoin(User, col(User.id) == col(AuditLog.actor_id))
        .where(*conditions)
        .order_by(col(AuditLog.occurred_at).desc(), col(AuditLog.id).desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return [(entry, email, name) for entry, email, name in rows], count
