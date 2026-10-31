import uuid

from sqlmodel import Session, col, func, select

from app.models import get_datetime_utc
from app.modules.notifications.errors import NotificationNotFound
from app.modules.notifications.models import Notification
from app.modules.notifications.schemas import NotificationPublic
from app.modules.ordering.models import Order


def list_notifications(
    session: Session,
    *,
    owner_id: uuid.UUID,
    unread_only: bool = False,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[NotificationPublic], int, int]:
    conditions = [Notification.owner_id == owner_id]
    if unread_only:
        conditions.append(Notification.read_at.is_(None))

    count = session.exec(
        select(func.count()).select_from(Notification).where(*conditions)
    ).one()
    unread_count = session.exec(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.owner_id == owner_id,
            Notification.read_at.is_(None),
        )
    ).one()
    rows = session.exec(
        select(Notification, Order.number)
        .join(Order, col(Order.id) == col(Notification.order_id))
        .where(*conditions)
        .order_by(col(Notification.created_at).desc(), col(Notification.id).desc())
        .offset(skip)
        .limit(limit)
    ).all()
    data = [
        NotificationPublic.model_validate(
            notification, update={"order_number": order_number}
        )
        for notification, order_number in rows
    ]
    return data, count, unread_count


def set_read_state(
    session: Session,
    *,
    owner_id: uuid.UUID,
    notification_id: uuid.UUID,
    is_read: bool,
) -> NotificationPublic:
    notification = session.exec(
        select(Notification)
        .where(
            Notification.id == notification_id,
            Notification.owner_id == owner_id,
        )
        .with_for_update()
    ).first()
    if notification is None:
        raise NotificationNotFound()

    order_number = session.exec(
        select(Order.number).where(Order.id == notification.order_id)
    ).one()
    notification.read_at = get_datetime_utc() if is_read else None
    session.add(notification)
    session.commit()
    session.refresh(notification)
    return NotificationPublic.model_validate(
        notification, update={"order_number": order_number}
    )
