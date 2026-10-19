import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.inventory.models import InventoryRole, ItemType, Unit
from app.modules.inventory.schemas import InventoryItemCreate


def _item_data(**overrides: object) -> dict[str, object]:
    return {
        "name": "Test item",
        "category_id": uuid.uuid4(),
        "item_type": ItemType.INGREDIENT,
        "base_unit": Unit.G,
        "purchase_unit": Unit.G,
        "conversion_factor": Decimal("1"),
        **overrides,
    }


@pytest.mark.parametrize(
    "item_type",
    [ItemType.INGREDIENT, ItemType.PACKAGING, ItemType.CONSUMABLE],
)
def test_legacy_material_types_default_to_raw_material(item_type: ItemType) -> None:
    item = InventoryItemCreate.model_validate(_item_data(item_type=item_type))

    assert item.role == InventoryRole.RAW_MATERIAL


def test_legacy_merchandise_defaults_to_general() -> None:
    item = InventoryItemCreate.model_validate(
        _item_data(item_type=ItemType.MERCHANDISE)
    )

    assert item.role == InventoryRole.GENERAL


def test_finished_good_role_is_explicit() -> None:
    item = InventoryItemCreate.model_validate(
        _item_data(role=InventoryRole.FINISHED_GOOD)
    )

    assert item.role == InventoryRole.FINISHED_GOOD


def test_unknown_role_is_rejected() -> None:
    with pytest.raises(ValidationError):
        InventoryItemCreate.model_validate(_item_data(role="unknown"))
