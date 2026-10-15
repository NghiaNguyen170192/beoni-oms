import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models import get_datetime_utc


class AuditLog(SQLModel, table=True):
    """Append-only; a database trigger rejects UPDATE and DELETE."""

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_entity", "entity_type", "entity_id"),
        Index("ix_audit_log_occurred_at", "occurred_at"),
        Index("ix_audit_log_actor_id", "actor_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    actor_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="RESTRICT"
    )
    occurred_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        nullable=False,
    )
    entity_type: str = Field(max_length=64)
    entity_id: str = Field(max_length=64)
    action: str = Field(max_length=64)
    changes: dict[str, Any] | None = Field(default=None, sa_type=JSONB)
    request_id: str | None = Field(default=None, max_length=128)
