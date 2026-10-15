import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models import get_datetime_utc

SCOPE_KEY_CONSTRAINT = "uq_idempotency_keys_scope_key"


class IdempotencyKey(SQLModel, table=True):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("scope", "key", name=SCOPE_KEY_CONSTRAINT),
        Index("ix_idempotency_keys_created_at", "created_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    scope: str = Field(max_length=64)
    key: str = Field(max_length=255)
    request_hash: str = Field(max_length=64)
    response_status: int
    response_body: Any = Field(default=None, sa_type=JSONB, nullable=True)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        nullable=False,
    )
