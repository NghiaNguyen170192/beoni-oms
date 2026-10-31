import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models import get_datetime_utc


class Notification(SQLModel, table=True):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("owner_id", "order_id", name="uq_notifications_owner_order"),
        Index("ix_notifications_owner_created", "owner_id", "created_at"),
        Index("ix_notifications_owner_read", "owner_id", "read_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(foreign_key="user.id", ondelete="RESTRICT")
    order_id: uuid.UUID = Field(foreign_key="orders.id", ondelete="RESTRICT")
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        nullable=False,
    )
    read_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
