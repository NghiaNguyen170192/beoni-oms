import uuid
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.modules.audit.models import AuditLog
from app.modules.identity.roles import Role
from app.modules.ordering import service as ordering_service
from app.modules.ordering.models import Order, OrderFee, OrderType
from app.modules.ordering.schemas import OrderCreate
from app.modules.settings import service
from app.modules.settings.models import BusinessSettings, Language
from tests.utils.user import make_user_with_role

API = settings.API_V1_STR
URL = f"{API}/settings/business"
LANGUAGE_URL = f"{URL}/language"
BUSINESS_NAME_URL = f"{URL}/name"
BUSINESS_TAX_RATE_URL = f"{URL}/tax-rate"
ORDER_FEES_URL = f"{API}/settings/order-fees"
ORDER_FEES_ADMIN_URL = f"{ORDER_FEES_URL}/admin"
RoleHeaders = Callable[[Role], dict[str, str]]


@pytest.fixture()
def default_settings(db: Session) -> BusinessSettings:
    row = service.get_settings(db)
    row.sqlmodel_update(
        {
            "business_name": "Beoni",
            "currency_code": "VND",
            "timezone": "Asia/Ho_Chi_Minh",
            "allow_negative_stock": False,
            "tax_rate": Decimal("0"),
            "language": Language.EN,
        }
    )
    db.add(row)
    db.commit()
    return row


def _settings_audit_ids(db: Session) -> set[uuid.UUID]:
    return set(
        db.exec(
            select(AuditLog.id).where(AuditLog.entity_type == "business_settings")
        ).all()
    )


def _new_settings_audit_entries(db: Session, before: set[uuid.UUID]) -> list[AuditLog]:
    return [
        entry
        for entry in db.exec(
            select(AuditLog).where(AuditLog.entity_type == "business_settings")
        ).all()
        if entry.id not in before
    ]


def _payload(**overrides: Any) -> dict[str, Any]:
    return {
        "currency_code": "VND",
        "timezone": "Asia/Ho_Chi_Minh",
        "allow_negative_stock": False,
        **overrides,
    }


@pytest.mark.usefixtures("default_settings")
@pytest.mark.parametrize("role", list(Role))
def test_any_authenticated_user_reads_settings(
    client: TestClient,
    role_token_headers: RoleHeaders,
    role: Role,
) -> None:
    r = client.get(URL, headers=role_token_headers(role))

    assert r.status_code == 200
    body = r.json()
    assert body["currency_code"] == "VND"
    assert body["timezone"] == "Asia/Ho_Chi_Minh"


def test_unauthenticated_read_rejected(client: TestClient) -> None:
    assert client.get(URL).status_code == 401


@pytest.mark.usefixtures("default_settings")
def test_owner_enables_negative_stock_and_change_is_audited(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    before = _settings_audit_ids(db)

    r = client.put(
        URL, headers=superuser_token_headers, json=_payload(allow_negative_stock=True)
    )

    assert r.status_code == 200
    assert r.json()["allow_negative_stock"] is True
    assert service.get_settings(db).allow_negative_stock is True
    entries = _new_settings_audit_entries(db, before)
    assert [e.changes for e in entries] == [
        {"allow_negative_stock": {"old": False, "new": True}}
    ]


@pytest.mark.usefixtures("default_settings")
@pytest.mark.parametrize("role", [Role.OWNER, None])
def test_owner_sets_tax_rate_and_change_is_audited(
    client: TestClient,
    role_token_headers: RoleHeaders,
    superuser_token_headers: dict[str, str],
    db: Session,
    role: Role | None,
) -> None:
    before = _settings_audit_ids(db)

    r = client.put(
        BUSINESS_TAX_RATE_URL,
        headers=(
            superuser_token_headers if role is None else role_token_headers(role)
        ),
        json={"tax_rate": "8"},
    )

    assert r.status_code == 200
    assert r.json()["tax_rate"] == "8.00"
    entries = _new_settings_audit_entries(db, before)
    assert [e.changes for e in entries] == [
        {"tax_rate": {"old": "0.00", "new": "8.00"}}
    ]


@pytest.mark.usefixtures("default_settings")
def test_unchanged_update_writes_no_audit_entry(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    before = _settings_audit_ids(db)

    r = client.put(URL, headers=superuser_token_headers, json=_payload())

    assert r.status_code == 200
    assert _new_settings_audit_entries(db, before) == []


@pytest.mark.usefixtures("default_settings")
@pytest.mark.parametrize(
    "role", [Role.MANAGER, Role.CASHIER, Role.ACCOUNTANT, Role.INVENTORY_STAFF]
)
def test_non_owner_cannot_update_settings(
    client: TestClient,
    role_token_headers: RoleHeaders,
    db: Session,
    role: Role,
) -> None:
    r = client.put(
        URL, headers=role_token_headers(role), json=_payload(allow_negative_stock=True)
    )

    assert r.status_code == 403
    assert service.get_settings(db).allow_negative_stock is False


@pytest.mark.usefixtures("default_settings")
@pytest.mark.parametrize(
    "overrides",
    [
        {"timezone": "Mars/Olympus"},
        {"timezone": ""},
        {"currency_code": "XYZ"},
        {"currency_code": "USD"},
    ],
)
def test_invalid_settings_rejected(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    overrides: dict[str, Any],
) -> None:
    r = client.put(URL, headers=superuser_token_headers, json=_payload(**overrides))

    assert r.status_code == 422
    assert service.get_settings(db).timezone == "Asia/Ho_Chi_Minh"


@pytest.mark.usefixtures("default_settings")
@pytest.mark.parametrize("rate", ["-1", "100.5", "8.125", None])
def test_invalid_tax_rate_rejected(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    rate: str | None,
) -> None:
    r = client.put(
        BUSINESS_TAX_RATE_URL,
        headers=superuser_token_headers,
        json={"tax_rate": rate},
    )

    assert r.status_code == 422
    assert service.get_settings(db).tax_rate == Decimal("0")


@pytest.mark.usefixtures("default_settings")
@pytest.mark.parametrize(
    "role", [Role.MANAGER, Role.CASHIER, Role.ACCOUNTANT, Role.INVENTORY_STAFF]
)
def test_non_owner_cannot_update_tax_rate(
    client: TestClient,
    role_token_headers: RoleHeaders,
    db: Session,
    role: Role,
) -> None:
    r = client.put(
        BUSINESS_TAX_RATE_URL,
        headers=role_token_headers(role),
        json={"tax_rate": "8"},
    )

    assert r.status_code == 403
    assert service.get_settings(db).tax_rate == Decimal("0")


# Interface language


@pytest.mark.usefixtures("default_settings")
def test_owner_switches_language_and_change_is_audited(
    client: TestClient, role_token_headers: RoleHeaders, db: Session
) -> None:
    before = _settings_audit_ids(db)

    r = client.put(
        LANGUAGE_URL, headers=role_token_headers(Role.OWNER), json={"language": "vi"}
    )

    assert r.status_code == 200
    assert r.json()["language"] == "vi"
    reader = role_token_headers(Role.CASHIER)
    assert client.get(URL, headers=reader).json()["language"] == "vi"
    entries = _new_settings_audit_entries(db, before)
    assert [e.changes for e in entries] == [{"language": {"old": "en", "new": "vi"}}]


@pytest.mark.usefixtures("default_settings")
def test_full_settings_update_keeps_language(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    client.put(LANGUAGE_URL, headers=superuser_token_headers, json={"language": "vi"})

    r = client.put(URL, headers=superuser_token_headers, json=_payload())

    assert r.status_code == 200 and r.json()["language"] == "vi"


@pytest.mark.usefixtures("default_settings")
def test_business_settings_update_does_not_change_tax_rate(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    r = client.put(
        URL,
        headers=superuser_token_headers,
        json=_payload(tax_rate="8"),
    )

    assert r.status_code == 200
    assert service.get_settings(db).tax_rate == Decimal("0")


def test_owner_updates_business_name_separately_and_audits(
    client: TestClient,
    role_token_headers: RoleHeaders,
    db: Session,
) -> None:
    before = _settings_audit_ids(db)

    r = client.put(
        BUSINESS_NAME_URL,
        headers=role_token_headers(Role.OWNER),
        json={"business_name": "  Beoni Cafe  "},
    )

    assert r.status_code == 200
    assert r.json()["business_name"] == "Beoni Cafe"
    assert service.get_settings(db).business_name == "Beoni Cafe"
    entries = _new_settings_audit_entries(db, before)
    assert [entry.changes for entry in entries] == [
        {"business_name": {"old": "Beoni", "new": "Beoni Cafe"}}
    ]


@pytest.mark.parametrize("role", [Role.MANAGER, Role.CASHIER, Role.ACCOUNTANT])
def test_non_owner_cannot_update_business_name(
    client: TestClient,
    role_token_headers: RoleHeaders,
    db: Session,
    role: Role,
) -> None:
    r = client.put(
        BUSINESS_NAME_URL,
        headers=role_token_headers(role),
        json={"business_name": "New name"},
    )

    assert r.status_code == 403
    assert service.get_settings(db).business_name == "Beoni"


def test_blank_business_name_rejected(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.put(
        BUSINESS_NAME_URL,
        headers=superuser_token_headers,
        json={"business_name": "  "},
    )

    assert r.status_code == 422


def test_owner_manages_fee_types_and_pos_lists_enabled_only(
    client: TestClient,
    role_token_headers: RoleHeaders,
    db: Session,
) -> None:
    owner = role_token_headers(Role.OWNER)
    cashier = role_token_headers(Role.CASHIER)

    created = client.post(
        ORDER_FEES_URL, headers=owner, json={"name": "  Shipping  "}
    )

    assert created.status_code == 201
    fee_type_id = created.json()["id"]
    assert created.json()["name"] == "Shipping"
    assert [row["name"] for row in client.get(
        ORDER_FEES_URL, headers=cashier
    ).json()] == ["Shipping"]

    updated = client.patch(
        f"{ORDER_FEES_URL}/{fee_type_id}",
        headers=owner,
        json={"name": "Delivery", "is_enabled": False},
    )

    assert updated.status_code == 200
    assert updated.json()["name"] == "Delivery"
    assert updated.json()["is_enabled"] is False
    assert client.get(ORDER_FEES_URL, headers=cashier).json() == []
    assert client.get(ORDER_FEES_ADMIN_URL, headers=owner).json() == [
        updated.json()
    ]

    entries = list(
        db.exec(
            select(AuditLog)
            .where(AuditLog.entity_type == "order_fee_type")
            .order_by(AuditLog.occurred_at)
        ).all()
    )
    assert [entry.action for entry in entries] == ["created", "updated"]
    assert entries[1].changes == {
        "name": {"old": "Shipping", "new": "Delivery"},
        "is_enabled": {"old": True, "new": False},
    }


def test_non_owner_cannot_manage_fee_types(
    client: TestClient,
    role_token_headers: RoleHeaders,
) -> None:
    manager = role_token_headers(Role.MANAGER)

    assert client.get(ORDER_FEES_ADMIN_URL, headers=manager).status_code == 403
    assert (
        client.post(ORDER_FEES_URL, headers=manager, json={"name": "Shipping"}).status_code
        == 403
    )
    assert (
        client.patch(
            f"{ORDER_FEES_URL}/{uuid.uuid4()}",
            headers=manager,
            json={"is_enabled": False},
        ).status_code
        == 403
    )


def test_disabling_fee_preserves_existing_order_snapshot(
    client: TestClient,
    role_token_headers: RoleHeaders,
    db: Session,
) -> None:
    owner = role_token_headers(Role.OWNER)
    created = client.post(
        ORDER_FEES_URL, headers=owner, json={"name": "Shipping"}
    )
    fee_type_id = uuid.UUID(created.json()["id"])
    cashier = make_user_with_role(db, Role.CASHIER)
    order_public = ordering_service.create_order(
        db,
        data=OrderCreate(order_type=OrderType.TAKEAWAY),
        actor=cashier,
    )
    order = db.get(Order, order_public.id)
    assert order is not None
    db.add(
        OrderFee(
            order_id=order.id,
            fee_type_id=fee_type_id,
            fee_name="Shipping",
            amount=Decimal("25000"),
        )
    )
    order.fee_total = Decimal("25000")
    order.total = Decimal("25000")
    db.add(order)
    db.commit()

    updated = client.patch(
        f"{ORDER_FEES_URL}/{fee_type_id}",
        headers=owner,
        json={"name": "Delivery", "is_enabled": False},
    )

    assert updated.status_code == 200
    db.refresh(order)
    [snapshot] = db.exec(
        select(OrderFee).where(OrderFee.order_id == order.id)
    ).all()
    assert (snapshot.fee_name, snapshot.amount) == ("Shipping", Decimal("25000.00"))
    assert order.fee_total == order.total == Decimal("25000.00")


@pytest.mark.usefixtures("default_settings")
@pytest.mark.parametrize("language", ["fr", "EN", "", None])
def test_unsupported_language_rejected(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    language: str | None,
) -> None:
    r = client.put(
        LANGUAGE_URL, headers=superuser_token_headers, json={"language": language}
    )

    assert r.status_code == 422
    assert service.get_settings(db).language == Language.EN


@pytest.mark.usefixtures("default_settings")
@pytest.mark.parametrize(
    "role", [Role.MANAGER, Role.CASHIER, Role.ACCOUNTANT, Role.INVENTORY_STAFF]
)
def test_non_owner_cannot_switch_language(
    client: TestClient, role_token_headers: RoleHeaders, db: Session, role: Role
) -> None:
    r = client.put(
        LANGUAGE_URL, headers=role_token_headers(role), json={"language": "vi"}
    )

    assert r.status_code == 403
    assert service.get_settings(db).language == Language.EN
