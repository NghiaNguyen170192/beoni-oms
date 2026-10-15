import re
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.modules.audit.models import AuditLog
from app.modules.catalog import service
from app.modules.catalog.errors import (
    CategoryNameTaken,
    MenuItemNotSellable,
)
from app.modules.catalog.models import MenuCategory, ProductType
from app.modules.catalog.schemas import (
    MenuCategoryCreate,
    MenuCategoryUpdate,
    MenuItemCreate,
    MenuItemUpdate,
)
from app.modules.identity.roles import Role
from tests.utils.catalog import make_category, make_menu_item
from tests.utils.user import make_user_with_role
from tests.utils.utils import random_lower_string


def _unique(prefix: str) -> str:
    return f"{prefix} {random_lower_string()[:10]}"


def test_seed_categories_exist(db: Session) -> None:
    names = {c.name for c in db.exec(select(MenuCategory)).all()}
    assert {"Cà phê", "Trà", "Đồ ăn", "Khác"} <= names


def test_create_category(db: Session) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    name = _unique("Sinh tố")

    category = service.create_category(
        db, data=MenuCategoryCreate(name=f"  {name}  ", sort_order=5), actor=manager
    )

    assert category.name == name
    assert category.is_active is True
    assert category in service.list_categories(db)


def test_duplicate_active_category_name_conflicts_case_insensitively(
    db: Session,
) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    name = _unique("Nước ép")
    service.create_category(db, data=MenuCategoryCreate(name=name), actor=manager)

    with pytest.raises(CategoryNameTaken):
        service.create_category(
            db, data=MenuCategoryCreate(name=name.upper()), actor=manager
        )


def test_inactive_category_name_can_be_reused(db: Session) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    name = _unique("Theo mùa")
    old = service.create_category(db, data=MenuCategoryCreate(name=name), actor=manager)
    service.update_category(
        db, category_id=old.id, data=MenuCategoryUpdate(is_active=False), actor=manager
    )

    new = service.create_category(db, data=MenuCategoryCreate(name=name), actor=manager)

    assert new.id != old.id
    with pytest.raises(CategoryNameTaken):
        service.update_category(
            db,
            category_id=old.id,
            data=MenuCategoryUpdate(is_active=True),
            actor=manager,
        )


def test_reorder_categories(db: Session) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    first, second = make_category(db), make_category(db)

    service.reorder_categories(db, category_ids=[second.id, first.id], actor=manager)

    db.refresh(first)
    db.refresh(second)
    assert (second.sort_order, first.sort_order) == (0, 1)


def test_create_prepared_drink(db: Session) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    category = make_category(db)

    item = service.create_item(
        db,
        data=MenuItemCreate(
            name="Cà phê sữa đá",
            category_id=category.id,
            price=Decimal("29000"),
            product_type=ProductType.PREPARED,
        ),
        actor=manager,
    )

    assert re.fullmatch(r"MENU-\d{5,}", item.code)
    assert item.price == Decimal("29000")
    assert item.product_type == ProductType.PREPARED
    assert item.is_active and item.is_available


def test_product_codes_are_sequential_and_ignore_client_input(db: Session) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    category = make_category(db)

    def create(**extra: Any) -> str:
        data = MenuItemCreate.model_validate(
            {
                "name": _unique("Bánh"),
                "category_id": category.id,
                "price": "1000",
                "product_type": ProductType.NON_STOCK,
                **extra,
            }
        )
        return service.create_item(db, data=data, actor=manager).code

    first, second = create(), create(code="MENU-00001")

    assert int(second.removeprefix("MENU-")) == int(first.removeprefix("MENU-")) + 1


@pytest.mark.parametrize("code", ["CF001", "MENU-1", "menu-00001"])
def test_database_rejects_malformed_product_codes(db: Session, code: str) -> None:
    with pytest.raises(IntegrityError, match="ck_menu_items_code_format"):
        make_menu_item(db, code=code)


def test_database_rejects_duplicate_product_codes(db: Session) -> None:
    existing = make_menu_item(db)

    with pytest.raises(IntegrityError):
        make_menu_item(db, code=existing.code)


def test_price_change_is_audited(db: Session) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    item = make_menu_item(db, price=Decimal("29000"))

    updated = service.update_item(
        db, item_id=item.id, data=MenuItemUpdate(price=Decimal("32000")), actor=manager
    )

    assert updated.price == Decimal("32000")
    entries = db.exec(
        select(AuditLog).where(
            AuditLog.entity_type == "menu_item",
            AuditLog.entity_id == str(item.id),
            AuditLog.action == "updated",
        )
    ).all()
    assert [e.changes for e in entries] == [
        {"price": {"old": "29000.00", "new": "32000.00"}}
    ]
    assert entries[0].actor_id == manager.id


def test_tracked_field_changes_are_audited_together(db: Session) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    item = make_menu_item(db)

    service.update_item(
        db,
        item_id=item.id,
        data=MenuItemUpdate(
            name="Renamed",
            product_type=ProductType.DIRECT_SALE,
            is_active=False,
            is_available=False,
        ),
        actor=manager,
    )

    entry = db.exec(
        select(AuditLog).where(
            AuditLog.entity_id == str(item.id), AuditLog.action == "updated"
        )
    ).one()
    assert entry.changes is not None
    assert set(entry.changes) == {"name", "product_type", "is_active", "is_available"}


def test_unchanged_update_writes_no_audit(db: Session) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    item = make_menu_item(db, price=Decimal("29000"))

    service.update_item(
        db, item_id=item.id, data=MenuItemUpdate(price=Decimal("29000")), actor=manager
    )

    assert (
        db.exec(
            select(AuditLog).where(
                AuditLog.entity_id == str(item.id), AuditLog.action == "updated"
            )
        ).first()
        is None
    )


def test_never_sold_item_can_be_deleted(db: Session) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    item = make_menu_item(db)

    service.delete_item(db, item_id=item.id, actor=manager)

    assert service.search_items(db, q=item.code)[1] == 0


def test_unavailable_item_is_not_sellable(db: Session) -> None:
    manager = make_user_with_role(db, Role.MANAGER)
    item = make_menu_item(db)
    assert service.get_sellable_item(db, item.id).id == item.id

    service.update_item(
        db, item_id=item.id, data=MenuItemUpdate(is_available=False), actor=manager
    )

    with pytest.raises(MenuItemNotSellable):
        service.get_sellable_item(db, item.id)
    _, count = service.search_items(db, q=item.code, sellable=True)
    assert count == 0


def test_search_by_partial_name_and_filters(db: Session) -> None:
    category = make_category(db)
    tag = random_lower_string()[:8]
    milk = make_menu_item(
        db,
        category=category,
        name=f"Cà phê sữa {tag}",
        product_type=ProductType.PREPARED,
    )
    make_menu_item(
        db,
        category=category,
        name=f"Bạc xỉu sữa {tag}",
        is_active=False,
        product_type=ProductType.PREPARED,
    )
    tea = make_menu_item(
        db, category=category, name=f"Trà đào {tag}", product_type=ProductType.NON_STOCK
    )

    items, count = service.search_items(db, q=f"sữa {tag}", is_active=True)
    assert (count, [i.id for i in items]) == (1, [milk.id])

    items, _ = service.search_items(
        db, category_id=category.id, product_type=ProductType.NON_STOCK
    )
    assert [i.id for i in items] == [tea.id]

    _, all_count = service.search_items(db, category_id=category.id)
    assert all_count == 3


def test_search_escapes_like_wildcards(db: Session) -> None:
    make_menu_item(db, name="Plain item")
    _, count = service.search_items(db, q="%")
    assert count == 0
