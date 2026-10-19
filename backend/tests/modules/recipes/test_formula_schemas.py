from datetime import datetime, timezone
from decimal import Decimal
import uuid

import pytest
from pydantic import ValidationError

from app.modules.recipes.schemas import RecipeVersionCreate


def _payload(**overrides: object) -> dict[str, object]:
    return {
        "menu_item_id": uuid.uuid4(),
        "effective_from": datetime.now(timezone.utc),
        "lines": [
            {"inventory_item_id": uuid.uuid4(), "quantity": Decimal("2.5")},
        ],
        **overrides,
    }


def test_legacy_recipe_version_without_outputs_remains_valid() -> None:
    recipe = RecipeVersionCreate.model_validate(_payload())

    assert recipe.outputs == []


def test_formula_version_accepts_multiple_menu_outputs() -> None:
    primary_menu_item_id = uuid.uuid4()
    outputs = [
        {
            "menu_item_id": primary_menu_item_id,
            "inventory_item_id": uuid.uuid4(),
            "quantity": Decimal("5"),
        },
        {
            "menu_item_id": uuid.uuid4(),
            "inventory_item_id": uuid.uuid4(),
            "quantity": Decimal("2"),
        },
    ]
    recipe = RecipeVersionCreate.model_validate(
        _payload(menu_item_id=primary_menu_item_id, outputs=outputs)
    )

    assert len(recipe.outputs) == 2
    assert recipe.outputs[0].quantity == Decimal("5")


def test_formula_outputs_must_include_primary_menu_item() -> None:
    with pytest.raises(ValidationError, match="must appear in outputs"):
        RecipeVersionCreate.model_validate(
            _payload(
                outputs=[
                    {
                        "menu_item_id": uuid.uuid4(),
                        "inventory_item_id": uuid.uuid4(),
                        "quantity": "1",
                    }
                ]
            )
        )


def test_formula_outputs_must_have_unique_menu_items() -> None:
    output_menu_item_id = uuid.uuid4()
    with pytest.raises(ValidationError, match="Each menu item"):
        RecipeVersionCreate.model_validate(
            _payload(
                menu_item_id=output_menu_item_id,
                outputs=[
                    {
                        "menu_item_id": output_menu_item_id,
                        "inventory_item_id": uuid.uuid4(),
                        "quantity": "1",
                    },
                    {
                        "menu_item_id": output_menu_item_id,
                        "inventory_item_id": uuid.uuid4(),
                        "quantity": "2",
                    },
                ],
            )
        )
