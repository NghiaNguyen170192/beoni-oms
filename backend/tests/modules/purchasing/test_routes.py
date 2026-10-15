import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.modules.identity.roles import Role
from tests.utils.inventory import make_inventory_item

API = f"{settings.API_V1_STR}/purchasing"
RoleHeaders = Callable[[Role], dict[str, str]]


def _supplier_payload() -> dict:
    return {"name": f"Supplier {uuid.uuid4().hex[:8]}", "phone": "0901234567"}


def test_cashier_cannot_read_suppliers(
    client: TestClient, role_token_headers: RoleHeaders
) -> None:
    response = client.get(
        f"{API}/suppliers", headers=role_token_headers(Role.CASHIER)
    )
    assert response.status_code == 403


def test_inventory_staff_creates_and_accountant_can_read(
    client: TestClient, role_token_headers: RoleHeaders
) -> None:
    created = client.post(
        f"{API}/suppliers",
        headers=role_token_headers(Role.INVENTORY_STAFF),
        json=_supplier_payload(),
    )
    assert created.status_code == 201
    supplier_id = created.json()["id"]
    read = client.get(
        f"{API}/suppliers/{supplier_id}",
        headers=role_token_headers(Role.ACCOUNTANT),
    )
    assert read.status_code == 200
    denied = client.post(
        f"{API}/suppliers",
        headers=role_token_headers(Role.ACCOUNTANT),
        json=_supplier_payload(),
    )
    assert denied.status_code == 403


def test_post_requires_key_and_staff_cannot_reverse(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    staff = role_token_headers(Role.INVENTORY_STAFF)
    supplier = client.post(
        f"{API}/suppliers", headers=staff, json=_supplier_payload()
    ).json()
    item = make_inventory_item(db)
    receipt = client.post(
        f"{API}/receipts",
        headers=staff,
        json={
            "supplier_id": supplier["id"],
            "receipt_date": "2026-10-15",
            "lines": [
                {
                    "item_id": str(item.id),
                    "purchase_quantity": "1",
                    "purchase_unit_cost": "10000",
                }
            ],
        },
    )
    assert receipt.status_code == 201
    receipt_id = receipt.json()["id"]
    missing_key = client.post(f"{API}/receipts/{receipt_id}/post", headers=staff)
    assert missing_key.status_code == 400
    posted = client.post(
        f"{API}/receipts/{receipt_id}/post",
        headers={**staff, "Idempotency-Key": uuid.uuid4().hex},
    )
    assert posted.status_code == 200
    assert posted.json()["payment_status"] == "unpaid"
    reverse = client.post(
        f"{API}/receipts/{receipt_id}/reverse",
        headers={**staff, "Idempotency-Key": uuid.uuid4().hex},
        json={"reason": "Not allowed"},
    )
    assert reverse.status_code == 403
    manager = role_token_headers(Role.MANAGER)
    allowed = client.post(
        f"{API}/receipts/{receipt_id}/reverse",
        headers={**manager, "Idempotency-Key": uuid.uuid4().hex},
        json={"reason": "Wrong item"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["status"] == "reversed"
