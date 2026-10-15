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
from app.modules.settings import service
from app.modules.settings.models import BusinessSettings, Language

API = settings.API_V1_STR
URL = f"{API}/settings/business"
LANGUAGE_URL = f"{URL}/language"
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
        "business_name": "Beoni",
        "currency_code": "VND",
        "timezone": "Asia/Ho_Chi_Minh",
        "allow_negative_stock": False,
        "tax_rate": "0",
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
def test_owner_sets_tax_rate_and_change_is_audited(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    before = _settings_audit_ids(db)

    r = client.put(URL, headers=superuser_token_headers, json=_payload(tax_rate="8"))

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
        {"business_name": "   "},
        {"tax_rate": "-1"},
        {"tax_rate": "100.5"},
        {"tax_rate": "8.125"},
        {"tax_rate": None},
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

    r = client.put(URL, headers=superuser_token_headers, json=_payload(tax_rate="8"))

    assert r.status_code == 200 and r.json()["language"] == "vi"


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
