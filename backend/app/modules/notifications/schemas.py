import uuid
from datetime import datetime

from sqlmodel import SQLModel


class NotificationPublic(SQLModel):
    id: uuid.UUID
    order_id: uuid.UUID
    order_number: str
    created_at: datetime
    read_at: datetime | None


class NotificationsPublic(SQLModel):
    data: list[NotificationPublic]
    count: int
    unread_count: int


class NotificationReadUpdate(SQLModel):
    is_read: bool
