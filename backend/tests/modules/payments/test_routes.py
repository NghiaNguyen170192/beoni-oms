import uuid
from collections.abc import Callable
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.modules.identity.roles import Role
from app.modules.settings import service as settings_service
from tests.utils.catalog import make_menu_item

API = settings.API_V1_STR
RoleHeaders = Callable[[Role], dict[str, str]]


def _key(headers: dict[str, str]) -> dict[str, str]:
    return {**headers, "Idempotency-Key": uuid.uuid4().hex}


def _cash_id(client: TestClient, headers: dict[str, str]) -> str:
    methods = client.get(f"{API}/payment-methods", headers=headers).json()["data"]
    return next(method["id"] for method in methods if method["kind"] == "cash")


def _sell(
    client: TestClient, db: Session, headers: dict[str, str], price: str = "29000"
) -> dict:
    item = make_menu_item(db, price=Decimal(price))
    order = client.post(
        f"{API}/orders/",
        headers=headers,
        json={
            "order_type": "takeaway",
            "lines": [{"menu_item_id": str(item.id), "quantity": "1"}],
        },
    )
    assert order.status_code == 201, order.text
    return order.json()


def test_owner_adds_and_deactivates_a_method_cashier_cannot(
    client: TestClient, role_token_headers: RoleHeaders
) -> None:
    owner = role_token_headers(Role.OWNER)
    name = f"Card {uuid.uuid4().hex[:6]}"
    created = client.post(
        f"{API}/payment-methods",
        headers=owner,
        json={"name": name, "kind": "other"},
    )
    assert created.status_code == 201
    method_id = created.json()["id"]

    cashier = role_token_headers(Role.CASHIER)
    denied = client.post(
        f"{API}/payment-methods",
        headers=cashier,
        json={"name": f"Nope {uuid.uuid4().hex[:6]}", "kind": "other"},
    )
    assert denied.status_code == 403

    updated = client.patch(
        f"{API}/payment-methods/{method_id}",
        headers=owner,
        json={"is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False


def test_cashier_pays_manager_voids_and_accountant_reads_totals(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    settings_service.get_settings(db).tax_rate = Decimal("0")
    db.commit()
    cashier = role_token_headers(Role.CASHIER)
    accountant = role_token_headers(Role.ACCOUNTANT)
    cash_id = _cash_id(client, cashier)

    def cash_net() -> Decimal:
        listed = client.get(f"{API}/payments", headers=accountant)
        assert listed.status_code == 200
        totals = listed.json()["totals"]
        match = next((row["total"] for row in totals if row["method_id"] == cash_id), "0")
        return Decimal(match)

    before = cash_net()
    order = _sell(client, db, cashier, "83700")
    missing = client.post(
        f"{API}/orders/{order['id']}/payments",
        headers=cashier,
        json={"method_id": cash_id, "tendered": "100000"},
    )
    assert missing.status_code == 400

    paid = client.post(
        f"{API}/orders/{order['id']}/payments",
        headers=_key(cashier),
        json={"method_id": cash_id, "tendered": "100000"},
    )
    assert paid.status_code == 201, paid.text
    assert paid.json()["change_amount"] == "16300.00"

    staff = role_token_headers(Role.INVENTORY_STAFF)
    assert (
        client.post(
            f"{API}/payments/{paid.json()['id']}/void",
            headers=_key(staff),
            json={"reason": "no"},
        ).status_code
        == 403
    )

    manager = role_token_headers(Role.MANAGER)
    voided = client.post(
        f"{API}/payments/{paid.json()['id']}/void",
        headers=_key(manager),
        json={"reason": "entered twice"},
    )
    assert voided.status_code == 200
    assert voided.json()["status"] == "voided"

    again = _sell(client, db, cashier, "29000")
    done = client.post(
        f"{API}/orders/{again['id']}/pay-and-complete",
        headers=_key(cashier),
        json={"method_id": cash_id, "amount": "29000"},
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "completed"

    refund_denied = client.post(
        f"{API}/orders/{again['id']}/refunds",
        headers=_key(cashier),
        json={"method_id": cash_id, "amount": "10000", "reason": "spill"},
    )
    assert refund_denied.status_code == 403
    refunded = client.post(
        f"{API}/orders/{again['id']}/refunds",
        headers=_key(manager),
        json={"method_id": cash_id, "amount": "10000", "reason": "spill"},
    )
    assert refunded.status_code == 201, refunded.text

    listed = client.get(
        f"{API}/payments", headers=accountant, params={"order_id": again["id"]}
    )
    assert listed.status_code == 200
    order_rows = [row for row in listed.json()["data"] if row["status"] == "active"]
    assert sum(Decimal(row["amount"]) for row in order_rows) == Decimal("29000")
    refunds = client.get(
        f"{API}/refunds", headers=accountant, params={"order_id": again["id"]}
    )
    assert refunds.status_code == 200
    assert sum(Decimal(row["amount"]) for row in refunds.json()["data"]) == Decimal("10000")
    assert cash_net() - before == Decimal("19000.00")
