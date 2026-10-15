import uuid
from datetime import datetime
from typing import Any

from sqlmodel import SQLModel


class AuditLogPublic(SQLModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_email: str | None
    actor_name: str | None
    occurred_at: datetime
    entity_type: str
    entity_id: str
    action: str
    changes: dict[str, Any] | None
    request_id: str | None


class AuditLogsPublic(SQLModel):
    data: list[AuditLogPublic]
    count: int
