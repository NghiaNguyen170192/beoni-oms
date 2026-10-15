from app.core.errors import Conflict, Invalid, NotFound


class InventoryCategoryNotFound(NotFound):
    default_detail = "Inventory category not found"


class InventoryItemNotFound(NotFound):
    default_detail = "Inventory item not found"


class SkuTaken(Conflict):
    default_detail = "An inventory item with this SKU already exists"


class BarcodeTaken(Conflict):
    default_detail = "An inventory item with this barcode already exists"


class ItemHasMovements(Conflict):
    default_detail = "Inventory item has stock movements; deactivate it instead"


class InvalidUnitConversion(Invalid):
    default_detail = (
        "Conversion factor must be 1 when purchase and base units are equal"
    )


class ItemInactive(Invalid):
    default_detail = "Inventory item is inactive"


class NegativeStockNotAllowed(Conflict):
    default_detail = "Stock would become negative and negative stock is not allowed"


class AdjustmentNotFound(NotFound):
    default_detail = "Stock adjustment not found"


class AdjustmentAlreadyReversed(Conflict):
    default_detail = "Stock adjustment has already been reversed"
