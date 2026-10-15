import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select as sa_select
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, or_, select

from app.core.config import settings
from app.core.errors import Invalid, is_foreign_key_violation, violated_constraint
from app.models import User, get_datetime_utc
from app.modules.audit import service as audit
from app.modules.catalog.errors import (
    CategoryInactive,
    CategoryNameTaken,
    CategoryNotFound,
    ImageTooLarge,
    InvalidImage,
    MenuItemCodeTaken,
    MenuItemInUse,
    MenuItemNotFound,
    MenuItemNotSellable,
)
from app.modules.catalog.models import (
    CATEGORY_ACTIVE_NAME_INDEX,
    ITEM_CODE_CONSTRAINT,
    ITEM_CODE_PREFIX,
    ITEM_CODE_SEQUENCE,
    MenuCategory,
    MenuItem,
    ProductType,
)
from app.modules.catalog.schemas import (
    MAX_IMAGE_BYTES,
    MenuCategoryCreate,
    MenuCategoryUpdate,
    MenuItemCreate,
    MenuItemUpdate,
)

_CATEGORY_FIELDS = ("name", "sort_order", "is_active")
_ITEM_FIELDS = (
    "code",
    "name",
    "description",
    "category_id",
    "price",
    "product_type",
    "is_active",
    "is_available",
)
MENU_IMAGE_DIR = "menu"


def _flush_or_conflict(session: Session) -> None:
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        constraint = violated_constraint(exc)
        if constraint == CATEGORY_ACTIVE_NAME_INDEX:
            raise CategoryNameTaken() from exc
        if constraint == ITEM_CODE_CONSTRAINT:
            raise MenuItemCodeTaken() from exc
        raise


def like_pattern(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


# Categories


def get_category(session: Session, category_id: uuid.UUID) -> MenuCategory:
    category = session.get(MenuCategory, category_id)
    if category is None:
        raise CategoryNotFound()
    return category


def _assert_name_free(
    session: Session, name: str, *, exclude_id: uuid.UUID | None = None
) -> None:
    query = select(MenuCategory.id).where(
        func.lower(MenuCategory.name) == name.lower(),
        col(MenuCategory.is_active).is_(True),
    )
    if exclude_id is not None:
        query = query.where(MenuCategory.id != exclude_id)
    if session.exec(query).first() is not None:
        raise CategoryNameTaken()


def list_categories(
    session: Session, *, include_inactive: bool = False
) -> list[MenuCategory]:
    query = select(MenuCategory)
    if not include_inactive:
        query = query.where(col(MenuCategory.is_active).is_(True))
    return list(
        session.exec(
            query.order_by(col(MenuCategory.sort_order), col(MenuCategory.name))
        ).all()
    )


def create_category(
    session: Session, *, data: MenuCategoryCreate, actor: User
) -> MenuCategory:
    _assert_name_free(session, data.name)
    category = MenuCategory.model_validate(data)
    session.add(category)
    _flush_or_conflict(session)
    audit.record(
        session,
        actor=actor,
        entity_type="menu_category",
        entity_id=category.id,
        action="created",
        changes={
            field: {"old": None, "new": getattr(category, field)}
            for field in _CATEGORY_FIELDS
        },
    )
    session.commit()
    session.refresh(category)
    return category


def update_category(
    session: Session, *, category_id: uuid.UUID, data: MenuCategoryUpdate, actor: User
) -> MenuCategory:
    category = get_category(session, category_id)
    old = category.model_dump()
    updates = data.model_dump(exclude_unset=True, exclude_none=True)
    new = {**old, **updates}
    changes = audit.diff(old, new, _CATEGORY_FIELDS)
    if not changes:
        return category
    if new["is_active"]:
        _assert_name_free(session, new["name"], exclude_id=category.id)
    category.sqlmodel_update(updates)
    category.updated_at = get_datetime_utc()
    session.add(category)
    _flush_or_conflict(session)
    audit.record(
        session,
        actor=actor,
        entity_type="menu_category",
        entity_id=category.id,
        action="updated",
        changes=changes,
    )
    session.commit()
    session.refresh(category)
    return category


def reorder_categories(
    session: Session, *, category_ids: list[uuid.UUID], actor: User
) -> list[MenuCategory]:
    """Set `sort_order` to each id's position in `category_ids`."""
    if len(set(category_ids)) != len(category_ids):
        raise Invalid("Category ids must be unique")
    categories = {
        c.id: c
        for c in session.exec(
            select(MenuCategory).where(col(MenuCategory.id).in_(category_ids))
        ).all()
    }
    if len(categories) != len(category_ids):
        raise CategoryNotFound()
    changes: dict[str, Any] = {}
    now = get_datetime_utc()
    for position, category_id in enumerate(category_ids):
        category = categories[category_id]
        if category.sort_order != position:
            changes[str(category_id)] = {"old": category.sort_order, "new": position}
            category.sort_order = position
            category.updated_at = now
            session.add(category)
    if changes:
        audit.record(
            session,
            actor=actor,
            entity_type="menu_category",
            entity_id="*",
            action="reordered",
            changes=changes,
        )
        session.commit()
    return list_categories(session, include_inactive=True)


# Items


def get_item(session: Session, item_id: uuid.UUID) -> MenuItem:
    item = session.get(MenuItem, item_id)
    if item is None:
        raise MenuItemNotFound()
    return item


def get_sellable_item(session: Session, item_id: uuid.UUID) -> MenuItem:
    """The item if it may be added to an order; raises otherwise."""
    item = get_item(session, item_id)
    if not (item.is_active and item.is_available):
        raise MenuItemNotSellable(f"Menu item {item.code} is inactive or unavailable")
    return item


def next_item_code(session: Session) -> str:
    """Reserve the next `MENU-NNNNN` code; numbers are never reused."""
    number = (
        session.connection()
        .execute(sa_select(ITEM_CODE_SEQUENCE.next_value()))
        .scalar_one()
    )
    return f"{ITEM_CODE_PREFIX}{number:05d}"


def _assert_category_usable(session: Session, category_id: uuid.UUID) -> None:
    if not get_category(session, category_id).is_active:
        raise CategoryInactive()


def search_items(
    session: Session,
    *,
    q: str | None = None,
    category_id: uuid.UUID | None = None,
    product_type: ProductType | None = None,
    is_active: bool | None = None,
    sellable: bool = False,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[MenuItem], int]:
    conditions: list[Any] = []
    if q and q.strip():
        pattern = like_pattern(q.strip())
        conditions.append(
            or_(
                col(MenuItem.name).ilike(pattern, escape="\\"),
                col(MenuItem.code).ilike(pattern, escape="\\"),
            )
        )
    if category_id is not None:
        conditions.append(col(MenuItem.category_id) == category_id)
    if product_type is not None:
        conditions.append(col(MenuItem.product_type) == product_type)
    if is_active is not None:
        conditions.append(col(MenuItem.is_active).is_(is_active))
    if sellable:
        conditions.append(col(MenuItem.is_active).is_(True))
        conditions.append(col(MenuItem.is_available).is_(True))

    count = session.exec(
        select(func.count()).select_from(MenuItem).where(*conditions)
    ).one()
    items = session.exec(
        select(MenuItem)
        .where(*conditions)
        .order_by(col(MenuItem.name), col(MenuItem.code))
        .offset(skip)
        .limit(limit)
    ).all()
    return list(items), count


def create_item(session: Session, *, data: MenuItemCreate, actor: User) -> MenuItem:
    _assert_category_usable(session, data.category_id)
    item = MenuItem.model_validate(data, update={"code": next_item_code(session)})
    session.add(item)
    _flush_or_conflict(session)
    audit.record(
        session,
        actor=actor,
        entity_type="menu_item",
        entity_id=item.id,
        action="created",
        changes={
            field: {"old": None, "new": getattr(item, field)} for field in _ITEM_FIELDS
        },
    )
    session.commit()
    session.refresh(item)
    return item


def update_item(
    session: Session, *, item_id: uuid.UUID, data: MenuItemUpdate, actor: User
) -> MenuItem:
    item = get_item(session, item_id)
    old = item.model_dump()
    updates = data.model_dump(exclude_unset=True)
    # Only description may be cleared; other fields ignore explicit nulls.
    updates = {k: v for k, v in updates.items() if v is not None or k == "description"}
    changes = audit.diff(old, {**old, **updates}, _ITEM_FIELDS)
    if not changes:
        return item
    if "category_id" in changes:
        _assert_category_usable(session, updates["category_id"])
    item.sqlmodel_update(updates)
    item.updated_at = get_datetime_utc()
    session.add(item)
    _flush_or_conflict(session)
    audit.record(
        session,
        actor=actor,
        entity_type="menu_item",
        entity_id=item.id,
        action="updated",
        changes=changes,
    )
    session.commit()
    session.refresh(item)
    return item


def _media_path(relative: str) -> Path:
    return Path(settings.MEDIA_ROOT) / relative


def _remove_media(relative: str | None) -> None:
    if relative:
        _media_path(relative).unlink(missing_ok=True)


def delete_item(session: Session, *, item_id: uuid.UUID, actor: User) -> None:
    """Delete a never-sold item. Order lines reference items with ON DELETE
    RESTRICT, so a sold item fails here and must be deactivated instead."""
    item = get_item(session, item_id)
    image_path = item.image_path
    snapshot = {field: getattr(item, field) for field in _ITEM_FIELDS}
    session.delete(item)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        if is_foreign_key_violation(exc):
            raise MenuItemInUse() from exc
        raise
    audit.record(
        session,
        actor=actor,
        entity_type="menu_item",
        entity_id=item_id,
        action="deleted",
        changes={
            field: {"old": value, "new": None} for field, value in snapshot.items()
        },
    )
    session.commit()
    _remove_media(image_path)


_IMAGE_SIGNATURES: tuple[tuple[str, str], ...] = (
    ("image/jpeg", "jpg"),
    ("image/png", "png"),
    ("image/webp", "webp"),
)


def detect_image_type(content: bytes) -> str | None:
    """File extension for a JPEG, PNG, or WebP payload, judged by magic bytes."""
    if content[:3] == b"\xff\xd8\xff":
        return "jpg"
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    return None


def set_item_image(
    session: Session,
    *,
    item_id: uuid.UUID,
    content: bytes,
    content_type: str | None,
    actor: User,
) -> MenuItem:
    item = get_item(session, item_id)
    if len(content) > MAX_IMAGE_BYTES:
        raise ImageTooLarge()
    extension = detect_image_type(content)
    allowed_types = {mime for mime, _ in _IMAGE_SIGNATURES}
    if extension is None or (content_type and content_type not in allowed_types):
        raise InvalidImage()

    relative = f"{MENU_IMAGE_DIR}/{uuid.uuid4().hex}.{extension}"
    target = _media_path(relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)

    old_path = item.image_path
    try:
        item.image_path = relative
        item.updated_at = get_datetime_utc()
        session.add(item)
        audit.record(
            session,
            actor=actor,
            entity_type="menu_item",
            entity_id=item.id,
            action="image_changed",
            changes={"image_path": {"old": old_path, "new": relative}},
        )
        session.commit()
    except BaseException:
        session.rollback()
        target.unlink(missing_ok=True)
        raise
    _remove_media(old_path)
    session.refresh(item)
    return item
