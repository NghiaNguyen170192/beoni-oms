import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.modules.catalog.models import ProductType
from app.modules.identity.roles import Role
from app.modules.inventory.models import Unit
from tests.utils.catalog import make_menu_item
from tests.utils.inventory import balance_of, make_inventory_item, seed_stock
from tests.utils.production import make_lot
from tests.utils.user import make_user_with_role

API = f"{settings.API_V1_STR}/recipes"
ORDERS = f"{settings.API_V1_STR}/orders"
D = Decimal


def _key(headers: dict[str, str]) -> dict[str, str]:
    return {**headers, "Idempotency-Key": uuid.uuid4().hex}


def _effective() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()


def _ingredient(db: Session, unit: Unit = Unit.G) -> str:
    item = make_inventory_item(
        db, base_unit=unit, purchase_unit=unit, conversion_factor=D("1")
    )
    return str(item.id)


def test_cashier_cannot_read_or_save_recipes(
    client: TestClient, db: Session, role_token_headers
) -> None:
    item = make_menu_item(db, product_type=ProductType.PREPARED)
    cashier = role_token_headers(Role.CASHIER)
    listed = client.get(
        f"{API}/", headers=cashier, params={"menu_item_id": str(item.id)}
    )
    created = client.post(
        f"{API}/",
        headers=cashier,
        json={
            "menu_item_id": str(item.id),
            "effective_from": _effective(),
            "lines": [{"inventory_item_id": _ingredient(db), "quantity": "18"}],
        },
    )
    assert listed.status_code == 403
    assert created.status_code == 403


def test_manager_saves_version_and_reads_cost(
    client: TestClient, db: Session, role_token_headers
) -> None:
    beans = make_inventory_item(
        db,
        name="Coffee beans",
        base_unit=Unit.G,
        purchase_unit=Unit.G,
        conversion_factor=D("1"),
    )
    seed_stock(db, beans, "1000", "400")
    other = make_inventory_item(
        db,
        name="Other",
        base_unit=Unit.PIECE,
        purchase_unit=Unit.PIECE,
        conversion_factor=D("1"),
    )
    seed_stock(db, other, "10", "3000")
    coffee = make_menu_item(db, product_type=ProductType.PREPARED)
    manager = role_token_headers(Role.MANAGER)

    created = client.post(
        f"{API}/",
        headers=manager,
        json={
            "menu_item_id": str(coffee.id),
            "effective_from": _effective(),
            "lines": [
                {"inventory_item_id": str(beans.id), "quantity": "18"},
                {"inventory_item_id": str(other.id), "quantity": "1"},
            ],
        },
    )
    assert created.status_code == 201, created.text
    recipe_id = created.json()["id"]
    assert created.json()["version"] == 1
    assert created.json()["kind"] == "recipe"

    listed = client.get(
        f"{API}/", headers=manager, params={"menu_item_id": str(coffee.id)}
    )
    assert listed.status_code == 200
    assert listed.json()["count"] == 1

    preview = client.get(f"{API}/{recipe_id}/cost-preview", headers=manager)
    assert preview.status_code == 200
    assert preview.json()["estimated_cost"] == "10200.00"

    invalid = client.post(
        f"{API}/",
        headers=manager,
        json={
            "menu_item_id": str(coffee.id),
            "effective_from": _effective(),
            "lines": [{"inventory_item_id": str(beans.id), "quantity": "0"}],
        },
    )
    assert invalid.status_code == 422

    plain = make_menu_item(db, product_type=ProductType.NON_STOCK)
    rejected = client.post(
        f"{API}/",
        headers=manager,
        json={
            "menu_item_id": str(plain.id),
            "effective_from": _effective(),
            "lines": [{"inventory_item_id": str(beans.id), "quantity": "1"}],
        },
    )
    assert rejected.status_code == 409


def _paid_shortage(
    client: TestClient, db: Session, headers: dict[str, str]
) -> tuple[str, str]:
    manager = make_user_with_role(db, Role.MANAGER)
    flan = make_menu_item(db, name="Flan", product_type=ProductType.DIRECT_SALE)
    _, _, flan_stock, _ = make_lot(db, manager, menu_item=flan, good=D("2"))
    order = client.post(
        f"{ORDERS}/",
        headers=headers,
        json={
            "order_type": "takeaway",
            "lines": [{"menu_item_id": str(flan.id), "quantity": "3"}],
        },
    )
    assert order.status_code == 201, order.text
    body = order.json()
    methods = client.get(
        f"{settings.API_V1_STR}/payment-methods", headers=headers
    ).json()["data"]
    cash = next(method["id"] for method in methods if method["kind"] == "cash")
    paid = client.post(
        f"{ORDERS}/{body['id']}/payments",
        headers=_key(headers),
        json={"method_id": cash, "amount": body["total"]},
    )
    assert paid.status_code == 201, paid.text
    return body["id"], str(flan_stock.id)


def test_complete_returns_structured_shortages(
    client: TestClient, db: Session, role_token_headers
) -> None:
    cashier = role_token_headers(Role.CASHIER)
    order_id, stock_id = _paid_shortage(client, db, cashier)

    response = client.post(f"{ORDERS}/{order_id}/complete", headers=_key(cashier))

    assert response.status_code == 409
    [shortage] = response.json()["shortages"]
    assert shortage["item"] == "Flan stock"
    assert Decimal(shortage["required"]) == D("3")
    assert Decimal(shortage["available"]) == D("2")
    assert shortage["unit"] == "piece"
    assert balance_of(db, uuid.UUID(stock_id)).quantity == D("2.0000")
    assert (
        client.get(f"{ORDERS}/{order_id}", headers=cashier).json()["status"] == "paid"
    )


def test_pay_and_complete_returns_the_same_shortage(
    client: TestClient, db: Session, role_token_headers
) -> None:
    cashier = role_token_headers(Role.CASHIER)
    manager = make_user_with_role(db, Role.MANAGER)
    flan = make_menu_item(db, name="Flan", product_type=ProductType.DIRECT_SALE)
    _, _, flan_stock, _ = make_lot(db, manager, menu_item=flan, good=D("2"))
    order = client.post(
        f"{ORDERS}/",
        headers=cashier,
        json={
            "order_type": "takeaway",
            "lines": [{"menu_item_id": str(flan.id), "quantity": "3"}],
        },
    ).json()
    methods = client.get(
        f"{settings.API_V1_STR}/payment-methods", headers=cashier
    ).json()["data"]
    cash = next(method["id"] for method in methods if method["kind"] == "cash")

    response = client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/pay-and-complete",
        headers=_key(cashier),
        json={"method_id": cash, "amount": order["total"]},
    )

    assert response.status_code == 409
    assert response.json()["shortages"][0]["item"] == "Flan stock"
    assert (
        client.get(f"{ORDERS}/{order['id']}", headers=cashier).json()["status"]
        == "draft"
    )
    assert balance_of(db, flan_stock.id).quantity == D("2.0000")


def test_stock_return_route_requires_permission_and_is_idempotent(
    client: TestClient, db: Session, role_token_headers
) -> None:
    manager_user = make_user_with_role(db, Role.MANAGER)
    flan = make_menu_item(db, name="Flan", product_type=ProductType.DIRECT_SALE)
    _, _, flan_stock, lot = make_lot(db, manager_user, menu_item=flan, good=D("3"))
    cashier = role_token_headers(Role.CASHIER)
    manager = role_token_headers(Role.MANAGER)
    order = client.post(
        f"{ORDERS}/",
        headers=cashier,
        json={
            "order_type": "takeaway",
            "lines": [{"menu_item_id": str(flan.id), "quantity": "1"}],
        },
    ).json()
    methods = client.get(
        f"{settings.API_V1_STR}/payment-methods", headers=cashier
    ).json()["data"]
    cash = next(method["id"] for method in methods if method["kind"] == "cash")
    assert (
        client.post(
            f"{ORDERS}/{order['id']}/payments",
            headers=_key(cashier),
            json={"method_id": cash, "amount": order["total"]},
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"{ORDERS}/{order['id']}/complete", headers=_key(cashier)
        ).status_code
        == 200
    )
    assert balance_of(db, flan_stock.id).quantity == D("2.0000")
    line_id = order["lines"][0]["id"]
    payload = {
        "reason": "unopened",
        "lines": [{"order_line_id": line_id, "quantity": "1", "sellable": True}],
    }
    denied = client.post(
        f"{ORDERS}/{order['id']}/stock-returns",
        headers=_key(cashier),
        json=payload,
    )
    assert denied.status_code == 403

    headers = _key(manager)
    first = client.post(
        f"{ORDERS}/{order['id']}/stock-returns", headers=headers, json=payload
    )
    second = client.post(
        f"{ORDERS}/{order['id']}/stock-returns", headers=headers, json=payload
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201
    assert first.json() == second.json()
    [return_line] = first.json()["lines"]
    assert return_line["finished_good_lot_id"] == str(lot.id)
    assert balance_of(db, flan_stock.id).quantity == D("3.0000")
    listed = client.get(f"{ORDERS}/{order['id']}/stock-returns", headers=manager)
    assert listed.status_code == 200
    assert listed.json()["count"] == 1
