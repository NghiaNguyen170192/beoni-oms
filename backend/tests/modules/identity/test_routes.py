from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.core.config import settings
from app.models import User
from app.modules.audit.models import AuditLog
from app.modules.identity.permissions import PERMISSIONS, Permission
from app.modules.identity.roles import Role
from tests.utils.user import create_user_with_role, make_user_with_role
from tests.utils.utils import random_email, random_lower_string

API = settings.API_V1_STR
RoleHeaders = Callable[[Role], dict[str, str]]


def _audit_entries(db: Session, user_id: object, action: str) -> list[AuditLog]:
    return list(
        db.exec(
            select(AuditLog).where(
                AuditLog.entity_type == "user",
                AuditLog.entity_id == str(user_id),
                AuditLog.action == action,
            )
        ).all()
    )


def test_me_includes_role_and_permissions(
    client: TestClient, role_token_headers: RoleHeaders
) -> None:
    r = client.get(f"{API}/users/me", headers=role_token_headers(Role.CASHIER))

    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "cashier"
    assert set(body["permissions"]) == {p.value for p in PERMISSIONS[Role.CASHIER]}


def test_superuser_me_is_owner_with_all_permissions(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    body = client.get(f"{API}/users/me", headers=superuser_token_headers).json()

    assert body["role"] == "owner"
    assert set(body["permissions"]) == {p.value for p in Permission}


def test_new_users_default_to_cashier(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"email": random_email(), "password": random_lower_string()}
    r = client.post(f"{API}/users/", headers=superuser_token_headers, json=data)

    assert r.status_code == 200
    assert r.json()["role"] == "cashier"


def test_owner_creates_user_with_role(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    data = {
        "email": random_email(),
        "password": random_lower_string(),
        "role": "inventory_staff",
    }
    r = client.post(f"{API}/users/", headers=superuser_token_headers, json=data)

    assert r.status_code == 200
    assert r.json()["role"] == "inventory_staff"
    created = _audit_entries(db, r.json()["id"], "created")
    assert len(created) == 1
    assert created[0].changes is not None
    assert created[0].changes["role"] == {"old": None, "new": "inventory_staff"}


def test_create_user_with_invalid_role_rejected(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    email = random_email()
    data = {"email": email, "password": random_lower_string(), "role": "chef"}
    r = client.post(f"{API}/users/", headers=superuser_token_headers, json=data)

    assert r.status_code == 422
    assert db.exec(select(User).where(User.email == email)).first() is None


def test_owner_changes_role_and_new_permissions_apply(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    user, headers = create_user_with_role(client=client, db=db, role=Role.CASHIER)

    r = client.patch(
        f"{API}/users/{user.id}",
        headers=superuser_token_headers,
        json={"role": "inventory_staff"},
    )

    assert r.status_code == 200
    assert r.json()["role"] == "inventory_staff"
    me = client.get(f"{API}/users/me", headers=headers).json()
    assert me["role"] == "inventory_staff"
    assert Permission.INVENTORY_ADJUST.value in me["permissions"]


def test_update_with_invalid_role_rejected(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    user = make_user_with_role(db, Role.CASHIER)

    r = client.patch(
        f"{API}/users/{user.id}", headers=superuser_token_headers, json={"role": "chef"}
    )

    assert r.status_code == 422
    db.refresh(user)
    assert user.role == Role.CASHIER


@pytest.mark.parametrize("actor_role", [Role.MANAGER, Role.ACCOUNTANT, Role.CASHIER])
def test_non_owner_cannot_change_roles(
    client: TestClient, role_token_headers: RoleHeaders, db: Session, actor_role: Role
) -> None:
    target = make_user_with_role(db, Role.CASHIER)

    r = client.patch(
        f"{API}/users/{target.id}",
        headers=role_token_headers(actor_role),
        json={"role": "manager"},
    )

    assert r.status_code == 403
    db.refresh(target)
    assert target.role == Role.CASHIER


def test_non_owner_cannot_create_users(
    client: TestClient, role_token_headers: RoleHeaders
) -> None:
    data = {"email": random_email(), "password": random_lower_string(), "role": "owner"}
    r = client.post(
        f"{API}/users/", headers=role_token_headers(Role.MANAGER), json=data
    )

    assert r.status_code == 403


def test_owner_cannot_change_own_role(client: TestClient, db: Session) -> None:
    owner, headers = create_user_with_role(client=client, db=db, role=Role.OWNER)

    r = client.patch(
        f"{API}/users/{owner.id}", headers=headers, json={"role": "cashier"}
    )

    assert r.status_code == 400
    db.refresh(owner)
    assert owner.role == Role.OWNER


def test_users_cannot_change_own_role_via_me(
    client: TestClient, role_token_headers: RoleHeaders
) -> None:
    headers = role_token_headers(Role.CASHIER)
    client.patch(f"{API}/users/me", headers=headers, json={"role": "owner"})

    assert client.get(f"{API}/users/me", headers=headers).json()["role"] == "cashier"


def test_signup_cannot_choose_role(client: TestClient, db: Session) -> None:
    email = random_email()
    data = {"email": email, "password": random_lower_string(), "role": "owner"}
    r = client.post(f"{API}/users/signup", json=data)

    assert r.status_code == 200
    user = db.exec(select(User).where(User.email == email)).one()
    assert user.role == Role.CASHIER


def test_unauthenticated_request_rejected(client: TestClient) -> None:
    r = client.get(f"{API}/users/")
    assert r.status_code == 401


def test_cashier_calling_owner_only_endpoint_directly_gets_403(
    client: TestClient, role_token_headers: RoleHeaders
) -> None:
    r = client.get(f"{API}/users/", headers=role_token_headers(Role.CASHIER))
    assert r.status_code == 403


def test_deactivated_user_token_rejected(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    user, headers = create_user_with_role(client=client, db=db, role=Role.CASHIER)
    assert client.get(f"{API}/users/me", headers=headers).status_code == 200

    r = client.patch(
        f"{API}/users/{user.id}",
        headers=superuser_token_headers,
        json={"is_active": False},
    )

    assert r.status_code == 200
    assert client.get(f"{API}/users/me", headers=headers).status_code == 400


def test_role_check_constraint(db: Session) -> None:
    user = make_user_with_role(db, Role.CASHIER)
    with pytest.raises(IntegrityError):
        db.connection().exec_driver_sql(
            "UPDATE \"user\" SET role = 'chef' WHERE id = %s", (user.id,)
        )
    db.rollback()


def test_superuser_must_be_owner_constraint(db: Session) -> None:
    user = make_user_with_role(db, Role.CASHIER)
    with pytest.raises(IntegrityError):
        db.connection().exec_driver_sql(
            'UPDATE "user" SET is_superuser = true WHERE id = %s', (user.id,)
        )
    db.rollback()


def test_promoting_to_superuser_sets_owner_role(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    user = make_user_with_role(db, Role.CASHIER)

    r = client.patch(
        f"{API}/users/{user.id}",
        headers=superuser_token_headers,
        json={"is_superuser": True},
    )

    assert r.status_code == 200
    assert r.json()["role"] == "owner"
    assert db.exec(
        select(AuditLog).where(
            AuditLog.entity_id == str(user.id),
            col(AuditLog.action) == "role_changed",
        )
    ).one()
