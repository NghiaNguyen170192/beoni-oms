import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.modules.audit.models import AuditLog
from app.modules.identity.roles import Role
from tests.utils.catalog import make_category, make_menu_item
from tests.utils.utils import random_lower_string

API = f"{settings.API_V1_STR}/catalog"
RoleHeaders = Callable[[Role], dict[str, str]]

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


@pytest.fixture(autouse=True)
def media_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path))
    return tmp_path


def _item_payload(category_id: Any, **overrides: Any) -> dict[str, Any]:
    return {
        "name": "Cà phê sữa đá",
        "category_id": str(category_id),
        "price": "29000",
        "product_type": "prepared",
        **overrides,
    }


# Categories


def test_manager_creates_category_and_cashier_lists_it(
    client: TestClient, role_token_headers: RoleHeaders
) -> None:
    name = f"Cà phê {random_lower_string()[:8]}"
    r = client.post(
        f"{API}/categories",
        headers=role_token_headers(Role.MANAGER),
        json={"name": name},
    )
    assert r.status_code == 201

    r = client.get(f"{API}/categories", headers=role_token_headers(Role.CASHIER))
    assert r.status_code == 200
    assert name in [c["name"] for c in r.json()["data"]]


def test_duplicate_category_returns_409(
    client: TestClient, role_token_headers: RoleHeaders
) -> None:
    headers = role_token_headers(Role.MANAGER)
    name = f"Trà {random_lower_string()[:8]}"
    assert (
        client.post(
            f"{API}/categories", headers=headers, json={"name": name}
        ).status_code
        == 201
    )

    r = client.post(f"{API}/categories", headers=headers, json={"name": name})
    assert r.status_code == 409


@pytest.mark.parametrize("role", [Role.CASHIER, Role.INVENTORY_STAFF, Role.ACCOUNTANT])
def test_non_managers_cannot_write_categories(
    client: TestClient, db: Session, role_token_headers: RoleHeaders, role: Role
) -> None:
    headers = role_token_headers(role)
    category = make_category(db)

    assert (
        client.post(
            f"{API}/categories", headers=headers, json={"name": "X"}
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"{API}/categories/{category.id}",
            headers=headers,
            json={"is_active": False},
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"{API}/categories/order",
            headers=headers,
            json={"category_ids": [str(category.id)]},
        ).status_code
        == 403
    )


def test_deactivated_category_hidden_unless_manager_asks(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    manager = role_token_headers(Role.MANAGER)
    category = make_category(db)
    r = client.patch(
        f"{API}/categories/{category.id}", headers=manager, json={"is_active": False}
    )
    assert r.status_code == 200

    ids = lambda r: [c["id"] for c in r.json()["data"]]  # noqa: E731
    assert str(category.id) not in ids(client.get(f"{API}/categories", headers=manager))
    assert str(category.id) in ids(
        client.get(f"{API}/categories?include_inactive=true", headers=manager)
    )
    cashier = role_token_headers(Role.CASHIER)
    assert str(category.id) not in ids(
        client.get(f"{API}/categories?include_inactive=true", headers=cashier)
    )


# Items


def test_create_item_assigns_code(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    headers = role_token_headers(Role.MANAGER)
    payload = _item_payload(make_category(db).id, code="MENU-00001")

    r = client.post(f"{API}/items", headers=headers, json=payload)
    assert r.status_code == 201
    body = r.json()
    assert re.fullmatch(r"MENU-\d{5,}", body["code"])
    assert body["price"] == "29000.00"
    assert body["is_active"] is True and body["is_available"] is True

    r = client.patch(
        f"{API}/items/{body['id']}", headers=headers, json={"code": "MENU-99999"}
    )
    assert r.status_code == 200 and r.json()["code"] == body["code"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"price": "-1000"},
        {"price": "10.123"},
        {"product_type": "combo"},
        {"name": "   "},
    ],
)
def test_invalid_items_rejected(
    client: TestClient,
    db: Session,
    role_token_headers: RoleHeaders,
    overrides: dict[str, Any],
) -> None:
    r = client.post(
        f"{API}/items",
        headers=role_token_headers(Role.MANAGER),
        json=_item_payload(make_category(db).id, **overrides),
    )
    assert r.status_code == 422


def test_unknown_category_rejected(
    client: TestClient, role_token_headers: RoleHeaders
) -> None:
    r = client.post(
        f"{API}/items",
        headers=role_token_headers(Role.MANAGER),
        json=_item_payload("00000000-0000-0000-0000-000000000000"),
    )
    assert r.status_code == 404


def test_cashier_cannot_write_items(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    headers = role_token_headers(Role.CASHIER)
    item = make_menu_item(db)

    assert (
        client.post(
            f"{API}/items", headers=headers, json=_item_payload(item.category_id)
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"{API}/items/{item.id}", headers=headers, json={"price": "1"}
        ).status_code
        == 403
    )
    assert client.delete(f"{API}/items/{item.id}", headers=headers).status_code == 403
    assert (
        client.post(
            f"{API}/items/{item.id}/image",
            headers=headers,
            files={"file": ("a.png", PNG, "image/png")},
        ).status_code
        == 403
    )


def test_price_change_audited_via_api(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    item = make_menu_item(db)

    r = client.patch(
        f"{API}/items/{item.id}",
        headers=role_token_headers(Role.MANAGER),
        json={"price": "32000"},
    )

    assert r.status_code == 200
    assert r.json()["price"] == "32000.00"
    entry = db.exec(
        select(AuditLog).where(
            AuditLog.entity_id == str(item.id), AuditLog.action == "updated"
        )
    ).one()
    assert entry.changes == {"price": {"old": "29000.00", "new": "32000.00"}}


def test_search_scoping_and_pagination(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    category = make_category(db)
    tag = random_lower_string()[:8]
    for n in range(3):
        make_menu_item(db, category=category, name=f"Sữa {tag} {n}")
    make_menu_item(db, category=category, name=f"Sữa {tag} off", is_active=False)
    make_menu_item(
        db, category=category, name=f"Sữa {tag} sold out", is_available=False
    )

    cashier = role_token_headers(Role.CASHIER)
    r = client.get(f"{API}/items", headers=cashier, params={"q": f"sữa {tag}"})
    assert r.json()["count"] == 4  # inactive hidden from non-managers

    r = client.get(
        f"{API}/items",
        headers=cashier,
        params={"q": f"sữa {tag}", "is_active": "false"},
    )
    assert r.json()["count"] == 4  # cashiers cannot ask for inactive items

    r = client.get(
        f"{API}/items",
        headers=cashier,
        params={"category_id": str(category.id), "sellable": "true", "limit": 2},
    )
    body = r.json()
    assert body["count"] == 3 and len(body["data"]) == 2

    manager = role_token_headers(Role.MANAGER)
    r = client.get(
        f"{API}/items", headers=manager, params={"category_id": str(category.id)}
    )
    assert r.json()["count"] == 5


def test_delete_never_sold_item(
    client: TestClient, db: Session, role_token_headers: RoleHeaders
) -> None:
    item = make_menu_item(db)
    headers = role_token_headers(Role.MANAGER)

    assert client.delete(f"{API}/items/{item.id}", headers=headers).status_code == 200
    assert client.get(f"{API}/items/{item.id}", headers=headers).status_code == 404


# Images


def test_upload_valid_image(
    client: TestClient,
    db: Session,
    role_token_headers: RoleHeaders,
    media_root: Path,
) -> None:
    item = make_menu_item(db)
    headers = role_token_headers(Role.MANAGER)

    r = client.post(
        f"{API}/items/{item.id}/image",
        headers=headers,
        files={"file": ("photo.png", PNG, "image/png")},
    )
    assert r.status_code == 200
    first = r.json()["image_path"]
    assert first.startswith("menu/") and first.endswith(".png")
    assert (media_root / first).read_bytes() == PNG

    r = client.post(
        f"{API}/items/{item.id}/image",
        headers=headers,
        files={"file": ("photo.jpg", JPEG, "image/jpeg")},
    )
    second = r.json()["image_path"]
    assert second.endswith(".jpg")
    assert not (media_root / first).exists()


def test_oversized_image_keeps_previous(
    client: TestClient,
    db: Session,
    role_token_headers: RoleHeaders,
    media_root: Path,
) -> None:
    item = make_menu_item(db)
    headers = role_token_headers(Role.MANAGER)
    first = client.post(
        f"{API}/items/{item.id}/image",
        headers=headers,
        files={"file": ("photo.png", PNG, "image/png")},
    ).json()["image_path"]

    big = PNG + b"\x00" * (5 * 1024 * 1024)
    r = client.post(
        f"{API}/items/{item.id}/image",
        headers=headers,
        files={"file": ("big.png", big, "image/png")},
    )

    assert r.status_code == 413
    db.refresh(item)
    assert item.image_path == first
    assert len(list((media_root / "menu").iterdir())) == 1


@pytest.mark.parametrize(
    ("filename", "content", "content_type"),
    [
        ("doc.pdf", b"%PDF-1.7 fake", "application/pdf"),
        ("fake.png", b"GIF89a" + b"\x00" * 32, "image/png"),
        ("anim.gif", b"GIF89a" + b"\x00" * 32, "image/gif"),
    ],
)
def test_wrong_image_type_rejected(
    client: TestClient,
    db: Session,
    role_token_headers: RoleHeaders,
    filename: str,
    content: bytes,
    content_type: str,
) -> None:
    item = make_menu_item(db)
    r = client.post(
        f"{API}/items/{item.id}/image",
        headers=role_token_headers(Role.MANAGER),
        files={"file": (filename, content, content_type)},
    )
    assert r.status_code == 422
    db.refresh(item)
    assert item.image_path is None
