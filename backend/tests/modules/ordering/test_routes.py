import uuid
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.modules.identity.roles import Role
from app.modules.settings import service as settings_service
from tests.utils.catalog import make_menu_item

API = f"{settings.API_V1_STR}/orders"
CATALOG = f"{settings.API_V1_STR}/catalog"
RoleHeaders = Callable[[Role], dict[str, str]]


@pytest.fixture(autouse=True)
def zero_tax(db: Session) -> None:
    row = settings_service.get_settings(db)
    row.tax_rate = Decimal("0")
    db.add(row)
    db.commit()


def _key(headers: dict[str, str], key: str | None = None) -> dict[str, str]:
    return {**headers, "Idempotency-Key": key or uuid.uuid4().hex}


def _new_order(
    client: TestClient, headers: dict[str, str], **body: Any
) -> dict[str, Any]:
    r = client.post(f"{API}/", headers=headers, json={"order_type": "takeaway", **body})
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def test_cashier_creates_order_with_lines_and_server_totals(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    coffee = make_menu_item(db, price=Decimal("29000"))
    tea = make_menu_item(db, price=Decimal("35000"))
    headers = role_token_headers(Role.CASHIER)

    order = _new_order(
        client,
        headers,
        lines=[
            {"menu_item_id": str(coffee.id), "quantity": "2"},
            {"menu_item_id": str(tea.id), "quantity": "1"},
        ],
        total="1",
        subtotal="1",
    )

    assert order["status"] == "draft"
    assert order["subtotal"] == "93000.00" and order["total"] == "93000.00"
    assert [line["line_total"] for line in order["lines"]] == ["58000.00", "35000.00"]


@pytest.mark.parametrize("quantity", ["0", "-1", "1.0001"])
def test_invalid_quantity_rejected(
    client: TestClient, db: Session, role_token_headers: RoleHeaders, quantity: str
) -> None:
    item = make_menu_item(db)
    headers = role_token_headers(Role.CASHIER)
    order = _new_order(client, headers)

    r = client.put(
        f"{API}/{order['id']}/lines",
        headers=headers,
        json={"lines": [{"menu_item_id": str(item.id), "quantity": quantity}]},
    )
    assert r.status_code == 422


def test_unavailable_item_rejected(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    item = make_menu_item(db, is_available=False)
    r = client.post(
        f"{API}/",
        headers=role_token_headers(Role.CASHIER),
        json={
            "order_type": "counter",
            "lines": [{"menu_item_id": str(item.id), "quantity": "1"}],
        },
    )
    assert r.status_code == 422


def test_cashier_discount_forbidden_manager_allowed(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    item = make_menu_item(db, price=Decimal("30000"))
    cashier = role_token_headers(Role.CASHIER)
    order = _new_order(
        client, cashier, lines=[{"menu_item_id": str(item.id), "quantity": "1"}]
    )
    discount = {"discount_type": "percent", "discount_value": "20"}

    r = client.put(f"{API}/{order['id']}/discount", headers=cashier, json=discount)
    assert r.status_code == 403

    manager = role_token_headers(Role.MANAGER)
    r = client.put(f"{API}/{order['id']}/discount", headers=manager, json=discount)
    assert r.status_code == 200
    assert r.json()["total"] == "24000.00"

    line_id = order["lines"][0]["id"]
    r = client.put(
        f"{API}/{order['id']}/lines/{line_id}/discount",
        headers=manager,
        json={"discount_type": "amount", "discount_value": "50000"},
    )
    assert r.status_code == 422


@pytest.mark.parametrize(
    "discount",
    [
        {"discount_type": "percent", "discount_value": "101"},
        {"discount_type": "percent", "discount_value": "-5"},
        {"discount_type": "amount"},
        {"discount_type": "coupon", "discount_value": "1"},
    ],
)
def test_invalid_discount_payloads(
    client: TestClient,
    role_token_headers: RoleHeaders,
    discount: dict[str, Any],
) -> None:
    manager = role_token_headers(Role.MANAGER)
    order = _new_order(client, manager)
    r = client.put(f"{API}/{order['id']}/discount", headers=manager, json=discount)
    assert r.status_code == 422


def test_complete_requires_key_and_is_idempotent(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    item = make_menu_item(db)
    headers = role_token_headers(Role.CASHIER)
    order = _new_order(
        client, headers, lines=[{"menu_item_id": str(item.id), "quantity": "1"}]
    )

    assert (
        client.post(f"{API}/{order['id']}/complete", headers=headers).status_code == 400
    )

    key = _key(headers, "complete-1")
    first = client.post(f"{API}/{order['id']}/complete", headers=key)
    second = client.post(f"{API}/{order['id']}/complete", headers=key)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["status"] == "completed"

    third = client.post(f"{API}/{order['id']}/complete", headers=_key(headers))
    assert third.status_code == 409

    r = client.put(
        f"{API}/{order['id']}/lines",
        headers=headers,
        json={"lines": [{"menu_item_id": str(item.id), "quantity": "2"}]},
    )
    assert r.status_code == 409


def test_empty_order_completion_rejected(
    client: TestClient, role_token_headers: RoleHeaders
) -> None:
    headers = role_token_headers(Role.CASHIER)
    order = _new_order(client, headers)
    r = client.post(f"{API}/{order['id']}/complete", headers=_key(headers))
    assert r.status_code == 422


def test_cancel_draft_and_reject_cancel_completed(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    item = make_menu_item(db)
    headers = role_token_headers(Role.CASHIER)
    draft = _new_order(client, headers)

    assert (
        client.post(
            f"{API}/{draft['id']}/cancel", headers=headers, json={"reason": " "}
        ).status_code
        == 422
    )
    r = client.post(
        f"{API}/{draft['id']}/cancel", headers=headers, json={"reason": "customer left"}
    )
    assert r.status_code == 200 and r.json()["status"] == "cancelled"

    done = _new_order(
        client, headers, lines=[{"menu_item_id": str(item.id), "quantity": "1"}]
    )
    client.post(f"{API}/{done['id']}/complete", headers=_key(headers))
    r = client.post(
        f"{API}/{done['id']}/cancel", headers=headers, json={"reason": "oops"}
    )
    assert r.status_code == 409
    assert (
        client.get(f"{API}/{done['id']}", headers=headers).json()["status"]
        == "completed"
    )


def test_inventory_staff_cannot_use_pos(
    client: TestClient, role_token_headers: RoleHeaders
) -> None:
    headers = role_token_headers(Role.INVENTORY_STAFF)
    assert (
        client.post(
            f"{API}/", headers=headers, json={"order_type": "counter"}
        ).status_code
        == 403
    )
    assert client.get(f"{API}/", headers=headers).status_code == 403


def test_accountant_reads_all_but_cannot_sell(
    client: TestClient, role_token_headers: RoleHeaders
) -> None:
    cashier = role_token_headers(Role.CASHIER)
    order = _new_order(client, cashier)
    accountant = role_token_headers(Role.ACCOUNTANT)

    assert client.get(f"{API}/{order['id']}", headers=accountant).status_code == 200
    assert (
        client.post(
            f"{API}/", headers=accountant, json={"order_type": "counter"}
        ).status_code
        == 403
    )
    r = client.post(
        f"{API}/{order['id']}/cancel", headers=accountant, json={"reason": "x"}
    )
    assert r.status_code == 403


def test_history_scoping_and_filters(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    item = make_menu_item(db)
    cashier_a = role_token_headers(Role.CASHIER)
    cashier_b = role_token_headers(Role.CASHIER)
    a1 = _new_order(client, cashier_a, order_type="dine_in", table_label="A1")
    a2 = _new_order(
        client, cashier_a, lines=[{"menu_item_id": str(item.id), "quantity": "1"}]
    )
    client.post(f"{API}/{a2['id']}/complete", headers=_key(cashier_a))
    b1 = _new_order(client, cashier_b)

    own = client.get(f"{API}/", headers=cashier_a, params={"limit": 500}).json()
    own_ids = [o["id"] for o in own["data"]]
    assert a1["id"] in own_ids and a2["id"] in own_ids and b1["id"] not in own_ids
    assert own_ids.index(a2["id"]) < own_ids.index(a1["id"])  # newest first
    listed_a1 = next(o for o in own["data"] if o["id"] == a1["id"])
    assert listed_a1["cashier_name"] == a1["cashier_name"]
    assert listed_a1["cashier_name"].startswith("Cashier ")

    assert client.get(f"{API}/{b1['id']}", headers=cashier_a).status_code == 404
    cashier_b_id = b1["cashier_id"]
    scoped = client.get(
        f"{API}/", headers=cashier_a, params={"cashier_id": cashier_b_id}
    ).json()
    assert b1["id"] not in [o["id"] for o in scoped["data"]]

    manager = role_token_headers(Role.MANAGER)
    by_b = client.get(
        f"{API}/", headers=manager, params={"cashier_id": cashier_b_id}
    ).json()
    assert [o["id"] for o in by_b["data"]] == [b1["id"]]

    completed = client.get(
        f"{API}/", headers=cashier_a, params={"status": "completed", "limit": 500}
    ).json()
    assert [o["id"] for o in completed["data"]] == [a2["id"]]
    dine_in = client.get(
        f"{API}/", headers=cashier_a, params={"order_type": "dine_in"}
    ).json()
    assert [o["id"] for o in dine_in["data"]] == [a1["id"]]
    by_number = client.get(
        f"{API}/", headers=manager, params={"number": a1["number"]}
    ).json()
    assert [o["id"] for o in by_number["data"]] == [a1["id"]]
    by_date = client.get(
        f"{API}/",
        headers=cashier_a,
        params={"date_from": a1["business_date"], "date_to": a1["business_date"]},
    ).json()
    assert by_date["count"] == 2


def test_receipt_endpoint(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    item = make_menu_item(db)
    headers = role_token_headers(Role.CASHIER)
    order = _new_order(
        client, headers, lines=[{"menu_item_id": str(item.id), "quantity": "1"}]
    )

    assert (
        client.get(f"{API}/{order['id']}/receipt", headers=headers).status_code == 409
    )
    client.post(f"{API}/{order['id']}/confirm", headers=headers)
    r = client.get(f"{API}/{order['id']}/receipt", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["order"]["number"] == order["number"]
    assert body["currency_code"] == "VND"


def test_sold_item_delete_rejected_via_api(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    item = make_menu_item(db)
    cashier = role_token_headers(Role.CASHIER)
    order = _new_order(
        client, cashier, lines=[{"menu_item_id": str(item.id), "quantity": "1"}]
    )
    client.post(f"{API}/{order['id']}/complete", headers=_key(cashier))

    r = client.delete(
        f"{CATALOG}/items/{item.id}", headers=role_token_headers(Role.MANAGER)
    )

    assert r.status_code == 409
    assert "deactivate" in r.json()["detail"]


def test_menu_price_change_leaves_completed_order_unchanged(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    item = make_menu_item(db, price=Decimal("29000"))
    cashier = role_token_headers(Role.CASHIER)
    order = _new_order(
        client, cashier, lines=[{"menu_item_id": str(item.id), "quantity": "2"}]
    )
    client.post(f"{API}/{order['id']}/complete", headers=_key(cashier))

    r = client.patch(
        f"{CATALOG}/items/{item.id}",
        headers=role_token_headers(Role.MANAGER),
        json={"price": "32000"},
    )
    assert r.status_code == 200

    after = client.get(f"{API}/{order['id']}", headers=cashier).json()
    assert after["lines"][0]["unit_price"] == "29000.00"
    assert after["total"] == "58000.00"
    assert after["subtotal"] == order["subtotal"]
