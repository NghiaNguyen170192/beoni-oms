import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.modules.identity.roles import Role
from app.modules.notifications.models import Notification
from app.modules.ordering import service as ordering
from app.modules.ordering.models import OrderType
from app.modules.ordering.schemas import OrderCreate
from tests.utils.user import make_user_with_role


def test_notification_requires_owner_and_order(db: Session) -> None:
    owner = make_user_with_role(db, Role.OWNER)
    cashier = make_user_with_role(db, Role.CASHIER)
    order = ordering.create_order(
        db, data=OrderCreate(order_type=OrderType.TAKEAWAY), actor=cashier
    )
    notification = Notification(owner_id=owner.id, order_id=order.id)

    db.add(notification)
    db.commit()

    saved = db.exec(select(Notification).where(Notification.id == notification.id)).one()
    assert saved.owner_id == owner.id
    assert saved.order_id == order.id
    assert saved.read_at is None


def test_notification_owner_order_pair_is_unique(db: Session) -> None:
    owner = make_user_with_role(db, Role.OWNER)
    cashier = make_user_with_role(db, Role.CASHIER)
    order = ordering.create_order(
        db, data=OrderCreate(order_type=OrderType.TAKEAWAY), actor=cashier
    )
    db.add(Notification(owner_id=owner.id, order_id=order.id))
    db.commit()

    db.add(Notification(owner_id=owner.id, order_id=order.id))
    with pytest.raises(IntegrityError, match="uq_notifications_owner_order"):
        db.commit()
    db.rollback()
