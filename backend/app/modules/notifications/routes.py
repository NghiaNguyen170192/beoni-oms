import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import SessionDep
from app.models import User
from app.modules.identity.dependencies import require_permission
from app.modules.identity.permissions import Permission
from app.modules.notifications import service
from app.modules.notifications.schemas import (
    NotificationPublic,
    NotificationReadUpdate,
    NotificationsPublic,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])
Owner = Annotated[User, Depends(require_permission(Permission.NOTIFICATIONS_READ))]


@router.get("", response_model=NotificationsPublic)
def read_notifications(
    session: SessionDep,
    owner: Owner,
    unread_only: bool = False,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> NotificationsPublic:
    data, count, unread_count = service.list_notifications(
        session,
        owner_id=owner.id,
        unread_only=unread_only,
        skip=skip,
        limit=limit,
    )
    return NotificationsPublic(data=data, count=count, unread_count=unread_count)


@router.patch("/{notification_id}", response_model=NotificationPublic)
def update_notification_read_state(
    session: SessionDep,
    owner: Owner,
    notification_id: uuid.UUID,
    update: NotificationReadUpdate,
) -> NotificationPublic:
    return service.set_read_state(
        session,
        owner_id=owner.id,
        notification_id=notification_id,
        is_read=update.is_read,
    )
