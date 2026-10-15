import uuid
from dataclasses import dataclass
from decimal import Decimal

from app.core.errors import Conflict, NotFound


class RecipeNotFound(NotFound):
    default_detail = "Recipe version not found"


class RecipeNotAllowed(Conflict):
    default_detail = "This menu item cannot have a recipe or stock link"


class DuplicateRecipeLine(Conflict):
    default_detail = "Each inventory item can appear only once in a version"


class VersionConflict(Conflict):
    default_detail = "A recipe version with this number or effective time exists"


class MissingConsumption(Conflict):
    def __init__(self, item_names: list[str]) -> None:
        names = ", ".join(item_names)
        super().__init__(f"No recipe or stock link for: {names}")


@dataclass(frozen=True)
class Shortage:
    item_id: uuid.UUID
    item: str
    sku: str
    required: Decimal
    available: Decimal
    unit: str


class InsufficientStock(Conflict):
    default_detail = "Insufficient stock"

    def __init__(self, shortages: list[Shortage]) -> None:
        payload = [
            {
                "item_id": str(row.item_id),
                "item": row.item,
                "sku": row.sku,
                "required": format(row.required, "f"),
                "available": format(row.available, "f"),
                "unit": row.unit,
            }
            for row in shortages
        ]
        super().__init__(self.default_detail, extra={"shortages": payload})
        self.shortages = shortages


class ReturnNotAllowed(Conflict):
    default_detail = "Stock can only be returned from a completed order"


class PreparedReturnRejected(Conflict):
    default_detail = "Only direct-sale items can be returned to stock"


class ReturnExceedsSold(Conflict):
    default_detail = "Return quantity exceeds the quantity still out"
