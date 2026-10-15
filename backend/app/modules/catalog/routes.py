import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, UploadFile

from app.api.deps import SessionDep
from app.models import Message, User
from app.modules.catalog import service
from app.modules.catalog.models import MenuCategory, MenuItem, ProductType
from app.modules.catalog.schemas import (
    MAX_IMAGE_BYTES,
    MenuCategoriesPublic,
    MenuCategoriesReorder,
    MenuCategoryCreate,
    MenuCategoryPublic,
    MenuCategoryUpdate,
    MenuItemCreate,
    MenuItemPublic,
    MenuItemsPublic,
    MenuItemUpdate,
)
from app.modules.identity.dependencies import require_permission
from app.modules.identity.permissions import Permission, has_permission

router = APIRouter(prefix="/catalog", tags=["catalog"])

Viewer = Annotated[User, Depends(require_permission(Permission.CATALOG_VIEW))]
Manager = Annotated[User, Depends(require_permission(Permission.CATALOG_MANAGE))]


# Categories


@router.get("/categories", response_model=MenuCategoriesPublic)
def read_categories(
    session: SessionDep, current_user: Viewer, include_inactive: bool = False
) -> Any:
    """
    Menu categories ordered for display. Inactive ones need catalog:manage.
    """
    include_inactive = include_inactive and has_permission(
        current_user, Permission.CATALOG_MANAGE
    )
    categories = service.list_categories(session, include_inactive=include_inactive)
    return MenuCategoriesPublic(
        data=[MenuCategoryPublic.model_validate(c) for c in categories],
        count=len(categories),
    )


@router.post("/categories", response_model=MenuCategoryPublic, status_code=201)
def create_category(
    session: SessionDep, actor: Manager, category_in: MenuCategoryCreate
) -> MenuCategory:
    return service.create_category(session, data=category_in, actor=actor)


@router.put("/categories/order", response_model=MenuCategoriesPublic)
def reorder_categories(
    session: SessionDep, actor: Manager, order_in: MenuCategoriesReorder
) -> Any:
    """
    Set display order: each category's position in `category_ids` becomes its sort order.
    """
    categories = service.reorder_categories(
        session, category_ids=order_in.category_ids, actor=actor
    )
    return MenuCategoriesPublic(
        data=[MenuCategoryPublic.model_validate(c) for c in categories],
        count=len(categories),
    )


@router.patch("/categories/{category_id}", response_model=MenuCategoryPublic)
def update_category(
    session: SessionDep,
    actor: Manager,
    category_id: uuid.UUID,
    category_in: MenuCategoryUpdate,
) -> MenuCategory:
    """
    Rename, reorder, activate, or deactivate a category.
    """
    return service.update_category(
        session, category_id=category_id, data=category_in, actor=actor
    )


# Items


@router.get("/items", response_model=MenuItemsPublic)
def read_items(
    session: SessionDep,
    current_user: Viewer,
    q: Annotated[str | None, Query(max_length=100)] = None,
    category_id: uuid.UUID | None = None,
    product_type: ProductType | None = None,
    is_active: bool | None = None,
    sellable: bool = False,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> Any:
    """
    Search items by name or code. Without catalog:manage only active items are
    returned; `sellable=true` limits to active and available items (the POS menu).
    """
    if not has_permission(current_user, Permission.CATALOG_MANAGE):
        is_active = True
    items, count = service.search_items(
        session,
        q=q,
        category_id=category_id,
        product_type=product_type,
        is_active=is_active,
        sellable=sellable,
        skip=skip,
        limit=limit,
    )
    return MenuItemsPublic(
        data=[MenuItemPublic.model_validate(i) for i in items], count=count
    )


@router.post("/items", response_model=MenuItemPublic, status_code=201)
def create_item(
    session: SessionDep, actor: Manager, item_in: MenuItemCreate
) -> MenuItem:
    return service.create_item(session, data=item_in, actor=actor)


@router.get("/items/{item_id}", response_model=MenuItemPublic)
def read_item(
    session: SessionDep, _current_user: Viewer, item_id: uuid.UUID
) -> MenuItem:
    return service.get_item(session, item_id)


@router.patch("/items/{item_id}", response_model=MenuItemPublic)
def update_item(
    session: SessionDep, actor: Manager, item_id: uuid.UUID, item_in: MenuItemUpdate
) -> MenuItem:
    """
    Update an item. Price, name, type, and status changes are audited.
    """
    return service.update_item(session, item_id=item_id, data=item_in, actor=actor)


@router.delete("/items/{item_id}", response_model=Message)
def delete_item(session: SessionDep, actor: Manager, item_id: uuid.UUID) -> Message:
    """
    Delete a never-sold item. Sold items are rejected with 409; deactivate them instead.
    """
    service.delete_item(session, item_id=item_id, actor=actor)
    return Message(message="Menu item deleted")


@router.post("/items/{item_id}/image", response_model=MenuItemPublic)
def upload_item_image(
    session: SessionDep, actor: Manager, item_id: uuid.UUID, file: UploadFile
) -> MenuItem:
    """
    Upload or replace the item's image (JPEG, PNG, or WebP; at most 2 MB).
    """
    content = file.file.read(MAX_IMAGE_BYTES + 1)
    return service.set_item_image(
        session,
        item_id=item_id,
        content=content,
        content_type=file.content_type,
        actor=actor,
    )
