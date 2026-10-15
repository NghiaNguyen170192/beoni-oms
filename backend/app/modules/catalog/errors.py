from app.core.errors import Conflict, DomainError, Invalid, NotFound


class CategoryNotFound(NotFound):
    default_detail = "Menu category not found"


class CategoryNameTaken(Conflict):
    default_detail = "An active menu category with this name already exists"


class CategoryInactive(Invalid):
    default_detail = "Menu category is inactive"


class MenuItemNotFound(NotFound):
    default_detail = "Menu item not found"


class MenuItemCodeTaken(Conflict):
    default_detail = "A menu item with this product code already exists"


class MenuItemInUse(Conflict):
    default_detail = (
        "Menu item has been sold or is referenced by other records; "
        "deactivate it instead"
    )


class MenuItemNotSellable(Invalid):
    default_detail = "Menu item is inactive or unavailable"


class InvalidImage(Invalid):
    default_detail = "Image must be a JPEG, PNG, or WebP file"


class ImageTooLarge(DomainError):
    status_code = 413
    default_detail = "Image must be at most 2 MB"
