from decimal import Decimal
from typing import Any

from sqlmodel import Session

from app.modules.catalog.models import MenuCategory, MenuItem, ProductType
from tests.utils.utils import random_code, random_lower_string


def make_category(db: Session, **overrides: Any) -> MenuCategory:
    category = MenuCategory(name=f"Cat {random_lower_string()[:12]}", **overrides)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def make_menu_item(
    db: Session, *, category: MenuCategory | None = None, **overrides: Any
) -> MenuItem:
    category = category or make_category(db)
    values: dict[str, Any] = {
        "code": random_code("MENU-"),
        "name": f"Item {random_lower_string()[:12]}",
        "category_id": category.id,
        "price": Decimal("29000"),
        # Non-stock so generic sale tests do not need a recipe. Prepared and
        # direct-sale items must pass product_type explicitly.
        "product_type": ProductType.NON_STOCK,
        **overrides,
    }
    item = MenuItem(**values)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
