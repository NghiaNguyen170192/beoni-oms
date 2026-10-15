import re
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.modules.identity.roles import Role
from app.modules.settings import service as settings_service
from tests.utils.inventory import (
    any_inventory_category,
    balance_of,
    make_inventory_item,
    seed_stock,
)
from tests.utils.utils import random_lower_string

API = f"{settings.API_V1_STR}/inventory"
RoleHeaders = Callable[[Role], dict[str, str]]


@pytest.fixture(autouse=True)
def disallow_negative_stock(db: Session) -> None:
    row = settings_service.get_settings(db)
    row.allow_negative_stock = False
    db.add(row)
    db.commit()


def _item_payload(db: Session, **overrides: Any) -> dict[str, Any]:
    return {
        "name": "Coffee beans",
        "category_id": str(any_inventory_category(db).id),
        "item_type": "ingredient",
        "base_unit": "g",
        "purchase_unit": "kg",
        "conversion_factor": "1000",
        **overrides,
    }


def _with_key(headers: dict[str, str]) -> dict[str, str]:
    return {**headers, "Idempotency-Key": uuid.uuid4().hex}


def test_create_item_assigns_sku_and_rejects_duplicate_barcode(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    headers = role_token_headers(Role.INVENTORY_STAFF)
    payload = _item_payload(
        db, sku="SP-00001", barcode=f"89{random_lower_string()[:10]}"
    )

    r = client.post(f"{API}/items", headers=headers, json=payload)
    assert r.status_code == 201
    body = r.json()
    assert re.fullmatch(r"SP-\d{5,}", body["sku"])
    assert body["quantity"] == "0.0000" and body["avg_unit_cost"] == "0.0000"

    assert client.post(f"{API}/items", headers=headers, json=payload).status_code == 409


@pytest.mark.parametrize(
    "overrides",
    [
        {"conversion_factor": "0"},
        {"conversion_factor": "-1"},
        {"conversion_factor": None},
        {"purchase_unit": "g", "conversion_factor": "1000"},
        {"base_unit": "gallon"},
        {"item_type": "service"},
        {"min_stock": "-1"},
    ],
)
def test_invalid_items_rejected(
    client: TestClient,
    db: Session,
    role_token_headers: RoleHeaders,
    overrides: dict[str, Any],
) -> None:
    payload = {k: v for k, v in _item_payload(db, **overrides).items() if v is not None}
    r = client.post(
        f"{API}/items", headers=role_token_headers(Role.MANAGER), json=payload
    )
    assert r.status_code == 422


def test_patch_ignores_quantity(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    item = make_inventory_item(db)
    seed_stock(db, item, "250", "2")

    r = client.patch(
        f"{API}/items/{item.id}",
        headers=role_token_headers(Role.MANAGER),
        json={"name": "Renamed", "quantity": "1", "value": "0"},
    )

    assert r.status_code == 200
    assert r.json()["quantity"] == "250.0000"


def test_cashier_has_no_inventory_access(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    headers = role_token_headers(Role.CASHIER)
    item = make_inventory_item(db)

    assert client.get(f"{API}/items", headers=headers).status_code == 403
    assert (
        client.post(f"{API}/items", headers=headers, json=_item_payload(db)).status_code
        == 403
    )
    r = client.post(
        f"{API}/adjustments",
        headers=_with_key(headers),
        json={
            "lines": [
                {"item_id": str(item.id), "reason": "spoilage", "quantity_change": "-1"}
            ]
        },
    )
    assert r.status_code == 403


def test_accountant_reads_but_cannot_write(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    headers = role_token_headers(Role.ACCOUNTANT)
    item = make_inventory_item(db)

    assert client.get(f"{API}/items/{item.id}", headers=headers).status_code == 200
    assert (
        client.get(f"{API}/items/{item.id}/movements", headers=headers).status_code
        == 200
    )
    assert (
        client.patch(
            f"{API}/items/{item.id}", headers=headers, json={"name": "x"}
        ).status_code
        == 403
    )
    assert client.delete(f"{API}/items/{item.id}", headers=headers).status_code == 403


def test_delete_item_with_history_rejected(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    item = make_inventory_item(db)
    seed_stock(db, item, "1", "1")

    r = client.delete(
        f"{API}/items/{item.id}", headers=role_token_headers(Role.MANAGER)
    )
    assert r.status_code == 409


def test_low_and_negative_stock_endpoints(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    from decimal import Decimal

    low = make_inventory_item(db, min_stock=Decimal("1000"))
    seed_stock(db, low, "500", "0.03")
    negative = make_inventory_item(db)
    seed_stock(db, negative, "-5")
    headers = role_token_headers(Role.INVENTORY_STAFF)

    low_ids = [
        i["id"]
        for i in client.get(
            f"{API}/low-stock", headers=headers, params={"limit": 500}
        ).json()["data"]
    ]
    negative_ids = [
        i["id"]
        for i in client.get(
            f"{API}/negative-stock", headers=headers, params={"limit": 500}
        ).json()["data"]
    ]

    assert str(low.id) in low_ids and str(negative.id) not in low_ids
    assert str(negative.id) in negative_ids and str(low.id) not in negative_ids


def test_movement_history_filters(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    item = make_inventory_item(db)
    seed_stock(db, item, "2000", "0.5")
    headers = role_token_headers(Role.INVENTORY_STAFF)
    client.post(
        f"{API}/adjustments",
        headers=_with_key(headers),
        json={
            "lines": [
                {
                    "item_id": str(item.id),
                    "reason": "spoilage",
                    "quantity_change": "-100",
                }
            ]
        },
    )

    r = client.get(
        f"{API}/items/{item.id}/movements",
        headers=headers,
        params={"movement_type": "adjustment"},
    )

    body = r.json()
    assert body["count"] == 1
    assert body["data"][0]["quantity"] == "-100.0000"
    assert body["data"][0]["quantity_after"] == "1900.0000"

    all_rows = client.get(f"{API}/items/{item.id}/movements", headers=headers).json()
    assert [m["quantity_after"] for m in all_rows["data"]] == ["1900.0000", "2000.0000"]


def test_post_adjustment_requires_idempotency_key(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    item = make_inventory_item(db)
    r = client.post(
        f"{API}/adjustments",
        headers=role_token_headers(Role.INVENTORY_STAFF),
        json={
            "lines": [
                {
                    "item_id": str(item.id),
                    "reason": "correction",
                    "quantity_change": "1",
                }
            ]
        },
    )
    assert r.status_code == 400


def test_post_adjustment_negative_stock_rejected(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    item = make_inventory_item(db)
    seed_stock(db, item, "5", "1")

    r = client.post(
        f"{API}/adjustments",
        headers=_with_key(role_token_headers(Role.INVENTORY_STAFF)),
        json={
            "lines": [
                {"item_id": str(item.id), "reason": "missing", "quantity_change": "-15"}
            ]
        },
    )

    assert r.status_code == 409
    assert "negative" in r.json()["detail"]
    assert balance_of(db, item.id).quantity == 5


def test_post_list_detail_and_reverse(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    item = make_inventory_item(db)
    seed_stock(db, item, "100", "1")
    staff = role_token_headers(Role.INVENTORY_STAFF)
    headers = _with_key(staff)
    payload = {
        "note": "Sữa hỏng",
        "lines": [
            {"item_id": str(item.id), "reason": "spoilage", "quantity_change": "-10"}
        ],
    }

    r = client.post(f"{API}/adjustments", headers=headers, json=payload)
    assert r.status_code == 201
    adjustment = r.json()
    repeat = client.post(f"{API}/adjustments", headers=headers, json=payload)
    assert repeat.status_code == 201 and repeat.json() == adjustment
    assert balance_of(db, item.id).quantity == 90

    listed = client.get(f"{API}/adjustments", headers=staff).json()
    summary = next(a for a in listed["data"] if a["id"] == adjustment["id"])
    assert summary["line_count"] == 1 and summary["status"] == "posted"
    assert summary["posted_by_name"].startswith("Inventory_Staff ")
    detail = client.get(f"{API}/adjustments/{adjustment['id']}", headers=staff).json()
    assert detail["lines"][0]["item_sku"] == item.sku
    assert detail["posted_by_name"] == summary["posted_by_name"]
    movements = client.get(f"{API}/items/{item.id}/movements", headers=staff).json()
    assert movements["data"][0]["actor_name"] == summary["posted_by_name"]

    r = client.post(
        f"{API}/adjustments/{adjustment['id']}/reverse",
        headers=_with_key(staff),
        json={},
    )
    assert r.status_code == 403  # inventory staff may not reverse

    manager = role_token_headers(Role.MANAGER)
    r = client.post(
        f"{API}/adjustments/{adjustment['id']}/reverse",
        headers=_with_key(manager),
        json={"note": "wrong item"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "reversed"
    assert balance_of(db, item.id).quantity == 100

    r = client.post(
        f"{API}/adjustments/{adjustment['id']}/reverse",
        headers=_with_key(manager),
        json={},
    )
    assert r.status_code == 409


def test_unknown_item_in_adjustment_returns_404(
    client: TestClient, role_token_headers: RoleHeaders
) -> None:
    r = client.post(
        f"{API}/adjustments",
        headers=_with_key(role_token_headers(Role.INVENTORY_STAFF)),
        json={
            "lines": [
                {
                    "item_id": str(uuid.uuid4()),
                    "reason": "correction",
                    "quantity_change": "1",
                }
            ]
        },
    )
    assert r.status_code == 404
