import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import User
from app.modules.identity.roles import Role
from app.modules.notifications.models import Notification
from app.modules.ordering import service as ordering_service
from app.modules.ordering.models import Order, OrderType
from app.modules.ordering.schemas import OrderCreate
from tests.utils.user import create_user_with_role, make_user_with_role

API = f"{settings.API_V1_STR}/notifications"
RoleHeaders = Callable[[Role], dict[str, str]]


def _create_order(db: Session) -> Order:
    cashier = make_user_with_role(db, Role.CASHIER)
    return ordering_service.create_order(
        db,
        data=OrderCreate(order_type=OrderType.TAKEAWAY),
        actor=cashier,
    )


def _add_notification(
    db: Session,
    *,
    owner: User,
    order_id: uuid.UUID,
    created_at: datetime,
    read_at: datetime | None = None,
) -> Notification:
    notification = Notification(
        owner_id=owner.id,
        order_id=order_id,
        created_at=created_at,
        read_at=read_at,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def test_owner_lists_paginated_notifications_and_updates_read_state(
    client: TestClient, db: Session
) -> None:
    owner, headers = create_user_with_role(client=client, db=db, role=Role.OWNER)
    other_owner, other_headers = create_user_with_role(
        client=client, db=db, role=Role.OWNER
    )
    now = datetime.now(timezone.utc)
    old_order = _create_order(db)
    newest_order = _create_order(db)
    other_order = _create_order(db)
    old = _add_notification(
        db,
        owner=owner,
        order_id=old_order.id,
        created_at=now - timedelta(minutes=2),
        read_at=now - timedelta(minutes=1),
    )
    newest = _add_notification(
        db,
        owner=owner,
        order_id=newest_order.id,
        created_at=now,
    )
    other = _add_notification(
        db,
        owner=other_owner,
        order_id=other_order.id,
        created_at=now + timedelta(seconds=1),
    )

    first_page = client.get(API, headers=headers, params={"limit": 1})
    assert first_page.status_code == 200
    first_page_body = first_page.json()
    assert first_page_body["count"] == 2
    assert first_page_body["unread_count"] == 1
    assert first_page_body["data"][0]["id"] == str(newest.id)
    assert first_page_body["data"][0]["order_id"] == str(newest_order.id)
    assert first_page_body["data"][0]["order_number"] == newest_order.number
    assert first_page_body["data"][0]["read_at"] is None

    second_page = client.get(API, headers=headers, params={"skip": 1, "limit": 1})
    assert second_page.status_code == 200
    assert second_page.json()["data"][0]["id"] == str(old.id)
    assert second_page.json()["unread_count"] == 1

    marked_unread = client.patch(
        f"{API}/{old.id}", headers=headers, json={"is_read": False}
    )
    assert marked_unread.status_code == 200
    assert marked_unread.json()["read_at"] is None

    marked_read = client.patch(
        f"{API}/{newest.id}", headers=headers, json={"is_read": True}
    )
    assert marked_read.status_code == 200
    assert marked_read.json()["read_at"] is not None

    unread = client.get(API, headers=headers, params={"unread_only": True})
    assert unread.status_code == 200
    assert unread.json()["count"] == 1
    assert unread.json()["data"][0]["id"] == str(old.id)

    assert client.patch(
        f"{API}/{other.id}", headers=headers, json={"is_read": True}
    ).status_code == 404
    other_list = client.get(API, headers=other_headers)
    assert other_list.status_code == 200
    assert [row["id"] for row in other_list.json()["data"]] == [str(other.id)]


def test_superuser_can_read_notifications(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(API, headers=superuser_token_headers)

    assert response.status_code == 200


@pytest.mark.parametrize(
    "role", [Role.CASHIER, Role.MANAGER, Role.ACCOUNTANT, Role.INVENTORY_STAFF]
)
def test_non_owner_cannot_read_notifications(
    client: TestClient, role_token_headers: RoleHeaders, role: Role
) -> None:
    response = client.get(API, headers=role_token_headers(role))

    assert response.status_code == 403
