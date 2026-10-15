import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.crud import get_user_by_email
from app.models import User
from app.modules.audit import service as audit
from app.modules.audit.models import AuditLog
from app.modules.identity.roles import Role
from tests.utils.user import make_user_with_role

API = settings.API_V1_STR
RoleHeaders = Callable[[Role], dict[str, str]]


def _superuser(db: Session) -> User:
    user = get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    assert user
    return user


def _seed(db: Session, actor: User, entity_id: str, n: int) -> list[AuditLog]:
    base = datetime.now(timezone.utc) - timedelta(minutes=10)
    entries = []
    for i in range(n):
        entry = audit.record(
            db,
            actor=actor,
            entity_type="order",
            entity_id=entity_id,
            action=f"step_{i}",
        )
        entry.occurred_at = base + timedelta(minutes=i)
        entries.append(entry)
    db.commit()
    return entries


def test_role_change_appears_in_audit_log(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    target = make_user_with_role(db, Role.CASHIER)
    client.patch(
        f"{API}/users/{target.id}",
        headers=superuser_token_headers,
        json={"role": "manager"},
    )

    r = client.get(
        f"{API}/audit-log/",
        headers=superuser_token_headers,
        params={"entity_type": "user", "entity_id": str(target.id)},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    [entry] = body["data"]
    assert entry["action"] == "role_changed"
    assert entry["actor_email"] == settings.FIRST_SUPERUSER
    assert entry["actor_name"] == _superuser(db).full_name
    assert entry["changes"] == {"role": {"old": "cashier", "new": "manager"}}
    assert entry["request_id"]


def test_deactivation_is_audited(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    target = make_user_with_role(db, Role.CASHIER)
    client.patch(
        f"{API}/users/{target.id}",
        headers=superuser_token_headers,
        json={"is_active": False},
    )

    body = client.get(
        f"{API}/audit-log/",
        headers=superuser_token_headers,
        params={"entity_id": str(target.id)},
    ).json()

    [entry] = body["data"]
    assert entry["action"] == "deactivated"
    assert entry["changes"] == {"is_active": {"old": True, "new": False}}


def test_filter_by_entity_returns_newest_first(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    order_id = str(uuid.uuid4())
    _seed(db, _superuser(db), order_id, 3)
    _seed(db, _superuser(db), str(uuid.uuid4()), 2)

    body = client.get(
        f"{API}/audit-log/",
        headers=superuser_token_headers,
        params={"entity_type": "order", "entity_id": order_id},
    ).json()

    assert body["count"] == 3
    assert [e["action"] for e in body["data"]] == ["step_2", "step_1", "step_0"]
    assert all(e["entity_id"] == order_id for e in body["data"])


def test_pagination_actor_and_date_filters(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    order_id = str(uuid.uuid4())
    entries = _seed(db, _superuser(db), order_id, 4)

    page = client.get(
        f"{API}/audit-log/",
        headers=superuser_token_headers,
        params={"entity_id": order_id, "skip": 1, "limit": 2},
    ).json()
    assert page["count"] == 4
    assert [e["action"] for e in page["data"]] == ["step_2", "step_1"]

    ranged = client.get(
        f"{API}/audit-log/",
        headers=superuser_token_headers,
        params={
            "entity_id": order_id,
            "actor_id": str(_superuser(db).id),
            "occurred_from": entries[1].occurred_at.isoformat(),
            "occurred_to": entries[3].occurred_at.isoformat(),
        },
    ).json()
    assert [e["action"] for e in ranged["data"]] == ["step_2", "step_1"]

    other_actor = client.get(
        f"{API}/audit-log/",
        headers=superuser_token_headers,
        params={"entity_id": order_id, "actor_id": str(uuid.uuid4())},
    ).json()
    assert other_actor["count"] == 0


@pytest.mark.parametrize(
    "role", [Role.CASHIER, Role.MANAGER, Role.ACCOUNTANT, Role.INVENTORY_STAFF]
)
def test_non_owner_denied(
    client: TestClient, role_token_headers: RoleHeaders, role: Role
) -> None:
    r = client.get(f"{API}/audit-log/", headers=role_token_headers(role))
    assert r.status_code == 403


def test_owner_role_user_can_read(
    client: TestClient, role_token_headers: RoleHeaders
) -> None:
    r = client.get(f"{API}/audit-log/", headers=role_token_headers(Role.OWNER))
    assert r.status_code == 200


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_no_mutation_endpoints(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    method: str,
) -> None:
    [entry] = _seed(db, _superuser(db), str(uuid.uuid4()), 1)

    r = client.request(
        method, f"{API}/audit-log/{entry.id}", headers=superuser_token_headers
    )

    assert r.status_code in (404, 405)
    db.refresh(entry)
    assert entry.action == "step_0"
