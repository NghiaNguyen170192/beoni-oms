import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.modules.catalog.models import MenuItem, ProductType
from app.modules.identity.roles import Role
from app.modules.inventory.models import (
    InventoryItem,
    InventoryMovement,
    InventoryRole,
    ItemType,
    Unit,
)
from app.modules.production.models import ProductionBatch, ProductionBatchStatus
from tests.utils.catalog import make_menu_item
from tests.utils.inventory import balance_of, make_inventory_item, seed_stock

API = f"{settings.API_V1_STR}/production/batches"
RoleHeaders = Callable[[Role], dict[str, str]]
D = Decimal


def _key(headers: dict[str, str], key: str | None = None) -> dict[str, str]:
    return {**headers, "Idempotency-Key": key or uuid.uuid4().hex}


def _batch_payload(
    db: Session, *, output_count: int = 1
) -> tuple[dict, tuple[InventoryItem, list[tuple[InventoryItem, MenuItem]]]]:
    ingredient = make_inventory_item(
        db,
        name="Batch flour",
        item_type=ItemType.INGREDIENT,
        role=InventoryRole.RAW_MATERIAL,
        base_unit=Unit.G,
        purchase_unit=Unit.KG,
        conversion_factor=D("1000"),
    )
    outputs = []
    for index in range(output_count):
        stock = make_inventory_item(
            db,
            name=f"Finished good {index}",
            item_type=ItemType.MERCHANDISE,
            role=InventoryRole.FINISHED_GOOD,
            base_unit=Unit.PIECE,
            purchase_unit=Unit.PIECE,
            conversion_factor=D("1"),
        )
        menu_item = make_menu_item(
            db,
            name=f"Batch menu item {index}",
            product_type=ProductType.DIRECT_SALE,
        )
        outputs.append((stock, menu_item))
    return (
        {
            "planned_for": datetime.now(timezone.utc).date().isoformat(),
            "ingredients": [
                {
                    "inventory_item_id": str(ingredient.id),
                    "planned_quantity": "3000",
                }
            ],
            "outputs": [
                {
                    "menu_item_id": str(menu_item.id),
                    "inventory_item_id": str(stock.id),
                    "planned_quantity": "5",
                }
                for stock, menu_item in outputs
            ],
        },
        [ingredient, outputs],
    )


def _create_batch(
    client: TestClient,
    db: Session,
    headers: dict[str, str],
    *,
    output_count: int = 1,
) -> tuple[dict, InventoryItem, list[tuple[InventoryItem, MenuItem]]]:
    payload, (ingredient, outputs) = _batch_payload(db, output_count=output_count)
    response = client.post(API, headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json(), ingredient, outputs


def _completion(batch: dict, *, finished_at: str | None = None) -> dict:
    body: dict[str, Any] = {
        "ingredients": [
            {
                "line_id": batch["ingredients"][0]["id"],
                "actual_quantity": "2500",
            }
        ],
        "outputs": [
            {
                "line_id": line["id"],
                "actual_good_quantity": "4",
                "waste_quantity": "1",
            }
            for line in batch["outputs"]
        ],
    }
    if finished_at is not None:
        body["finished_at"] = finished_at
    return body


def test_production_routes_enforce_role_permissions(
    client: TestClient,
    db: Session,
    role_token_headers: RoleHeaders,
) -> None:
    cashier = role_token_headers(Role.CASHIER)
    accountant = role_token_headers(Role.ACCOUNTANT)
    inventory_staff = role_token_headers(Role.INVENTORY_STAFF)
    manager = role_token_headers(Role.MANAGER)
    payload, _ = _batch_payload(db)

    assert client.get(API, headers=cashier).status_code == 403
    assert client.get(API, headers=accountant).status_code == 403
    assert client.post(API, headers=cashier, json=payload).status_code == 403
    created = client.post(API, headers=inventory_staff, json=payload)
    assert created.status_code == 201, created.text

    reverse = client.post(
        f"{API}/{created.json()['id']}/reverse",
        headers=_key(inventory_staff),
        json={"reason": "Not authorized"},
    )
    assert reverse.status_code == 403
    assert client.get(API, headers=manager).status_code == 200


def test_shared_batch_templates_can_be_created_selected_and_deleted(
    client: TestClient,
    db: Session,
    role_token_headers: RoleHeaders,
) -> None:
    manager = role_token_headers(Role.MANAGER)
    inventory_staff = role_token_headers(Role.INVENTORY_STAFF)
    cashier = role_token_headers(Role.CASHIER)
    payload, (ingredient, outputs) = _batch_payload(db, output_count=2)
    template_payload = {
        "name": " Morning production ",
        "ingredients": payload["ingredients"],
        "outputs": payload["outputs"],
    }
    url = f"{API}/templates"

    assert client.get(url, headers=cashier).status_code == 403
    created = client.post(url, headers=inventory_staff, json=template_payload)
    assert created.status_code == 201, created.text
    template = created.json()
    assert template["name"] == "Morning production"
    assert len(template["ingredients"]) == 1
    assert len(template["outputs"]) == 2

    listed = client.get(url, headers=manager)
    assert listed.status_code == 200
    assert listed.json() == {"data": [template], "count": 1}

    batch_payload = {
        "planned_for": datetime.now(timezone.utc).date().isoformat(),
        "ingredients": template["ingredients"],
        "outputs": template["outputs"],
    }
    batch = client.post(API, headers=inventory_staff, json=batch_payload)
    assert batch.status_code == 201, batch.text
    assert batch.json()["ingredients"][0]["inventory_item_id"] == str(ingredient.id)
    assert len(batch.json()["outputs"]) == len(outputs)

    template_url = f"{url}/{template['id']}"
    assert client.delete(template_url, headers=cashier).status_code == 403
    assert client.delete(template_url, headers=inventory_staff).status_code == 204
    assert client.get(url, headers=manager).json() == {"data": [], "count": 0}
    assert client.delete(template_url, headers=manager).status_code == 404


def test_complete_batch_api_handles_multiline_base_unit_quantities_and_retry(
    client: TestClient,
    db: Session,
    role_token_headers: RoleHeaders,
) -> None:
    staff = role_token_headers(Role.INVENTORY_STAFF)
    batch, ingredient, outputs = _create_batch(
        client, db, staff, output_count=2
    )
    seed_stock(db, ingredient, "3000", "2")
    body = _completion(batch)
    request_headers = _key(staff, "batch-complete-retry")

    completed = client.post(
        f"{API}/{batch['id']}/complete",
        headers=request_headers,
        json=body,
    )
    retry = client.post(
        f"{API}/{batch['id']}/complete",
        headers=request_headers,
        json=body,
    )

    assert completed.status_code == 200, completed.text
    assert retry.status_code == 200
    assert retry.json() == completed.json()
    assert len(completed.json()["outputs"]) == 2
    assert balance_of(db, ingredient.id).quantity == D("500")
    for stock, _menu_item in outputs:
        assert balance_of(db, stock.id).quantity == D("4")


def test_complete_batch_api_rejects_missing_key_invalid_state_and_shortage(
    client: TestClient,
    db: Session,
    role_token_headers: RoleHeaders,
) -> None:
    manager = role_token_headers(Role.MANAGER)
    batch, ingredient, _outputs = _create_batch(client, db, manager)
    complete_url = f"{API}/{batch['id']}/complete"
    body = _completion(batch)

    missing_key = client.post(complete_url, headers=manager, json=body)
    assert missing_key.status_code == 400
    invalid_quantity = _completion(batch)
    invalid_quantity["ingredients"][0]["actual_quantity"] = "-1"
    invalid = client.post(
        complete_url,
        headers=_key(manager),
        json=invalid_quantity,
    )
    assert invalid.status_code == 422
    shortage = client.post(
        complete_url,
        headers=_key(manager),
        json=body,
    )
    assert shortage.status_code == 409, shortage.text
    assert balance_of(db, ingredient.id).quantity == D("0")
    stored = db.get(ProductionBatch, uuid.UUID(batch["id"]))
    assert stored is not None
    assert stored.status == ProductionBatchStatus.DRAFT
    assert not db.exec(
        select(InventoryMovement).where(
            InventoryMovement.source_type == "production_batch",
            InventoryMovement.source_id == uuid.UUID(batch["id"]),
        )
    ).all()

    seed_stock(db, ingredient, "3000", "1")
    completed = client.post(complete_url, headers=_key(manager), json=body)
    assert completed.status_code == 200, completed.text
    already_completed = client.post(
        complete_url,
        headers=_key(manager),
        json=body,
    )
    assert already_completed.status_code == 409
    movements = db.exec(
        select(InventoryMovement).where(
            InventoryMovement.source_type == "production_batch",
            InventoryMovement.source_id == uuid.UUID(batch["id"]),
        )
    ).all()
    assert len(movements) == 2


def test_backdated_batch_completion_requires_permission(
    client: TestClient,
    db: Session,
    role_token_headers: RoleHeaders,
) -> None:
    inventory_staff = role_token_headers(Role.INVENTORY_STAFF)
    manager = role_token_headers(Role.MANAGER)
    batch, ingredient, _outputs = _create_batch(
        client, db, inventory_staff
    )
    seed_stock(db, ingredient, "3000", "1")
    body = _completion(
        batch,
        finished_at=(datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
    )

    denied = client.post(
        f"{API}/{batch['id']}/complete",
        headers=_key(inventory_staff, "backdated-batch"),
        json=body,
    )
    assert denied.status_code == 403
    allowed = client.post(
        f"{API}/{batch['id']}/complete",
        headers=_key(manager),
        json=body,
    )
    assert allowed.status_code == 200, allowed.text
