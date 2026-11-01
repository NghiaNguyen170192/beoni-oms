import uuid
from decimal import Decimal
from typing import Any

from sqlmodel import Session, col, select

from app.models import User, get_datetime_utc
from app.modules.audit import service as audit
from app.modules.settings.errors import OrderFeeTypeNotFound
from app.modules.settings.models import SETTINGS_ID, BusinessSettings, OrderFeeType
from app.modules.settings.schemas import (
    BusinessNameUpdate,
    BusinessSettingsUpdate,
    LanguageUpdate,
    OrderFeeTypeCreate,
    OrderFeeTypeUpdate,
)

_AUDITED_FIELDS = (
    "currency_code",
    "timezone",
    "allow_negative_stock",
)


def get_settings(session: Session, *, for_update: bool = False) -> BusinessSettings:
    settings = session.get(BusinessSettings, SETTINGS_ID, with_for_update=for_update)
    if settings is None:
        # The migration seeds this row; recreate defaults if it was removed.
        settings = BusinessSettings()
        session.add(settings)
        session.flush()
    return settings


def update_settings(
    session: Session, *, settings_in: BusinessSettingsUpdate, actor: User
) -> BusinessSettings:
    return _apply(session, settings_in.model_dump(), _AUDITED_FIELDS, actor)


def update_tax_rate(
    session: Session, *, tax_rate: Decimal, actor: User
) -> BusinessSettings:
    return _apply(session, {"tax_rate": tax_rate}, ("tax_rate",), actor)


def update_business_name(
    session: Session, *, name_in: BusinessNameUpdate, actor: User
) -> BusinessSettings:
    return _apply(
        session,
        name_in.model_dump(),
        ("business_name",),
        actor,
    )


def update_language(
    session: Session, *, language_in: LanguageUpdate, actor: User
) -> BusinessSettings:
    return _apply(session, language_in.model_dump(), ("language",), actor)


def list_order_fee_types(
    session: Session, *, include_disabled: bool = False
) -> list[OrderFeeType]:
    query = select(OrderFeeType)
    if not include_disabled:
        query = query.where(col(OrderFeeType.is_enabled).is_(True))
    return list(
        session.exec(query.order_by(col(OrderFeeType.name), col(OrderFeeType.id))).all()
    )


def create_order_fee_type(
    session: Session, *, data: OrderFeeTypeCreate, actor: User
) -> OrderFeeType:
    fee_type = OrderFeeType.model_validate(data)
    session.add(fee_type)
    session.flush()
    audit.record(
        session,
        actor=actor,
        entity_type="order_fee_type",
        entity_id=fee_type.id,
        action="created",
        changes={
            "name": {"old": None, "new": fee_type.name},
            "is_enabled": {"old": None, "new": fee_type.is_enabled},
        },
    )
    session.commit()
    session.refresh(fee_type)
    return fee_type


def update_order_fee_type(
    session: Session,
    *,
    fee_type_id: uuid.UUID,
    data: OrderFeeTypeUpdate,
    actor: User,
) -> OrderFeeType:
    fee_type = session.exec(
        select(OrderFeeType)
        .where(OrderFeeType.id == fee_type_id)
        .with_for_update()
    ).first()
    if fee_type is None:
        raise OrderFeeTypeNotFound()

    updates = data.model_dump(exclude_unset=True)
    old = fee_type.model_dump()
    changes = audit.diff(old, {**old, **updates}, updates)
    if changes:
        fee_type.sqlmodel_update(updates)
        fee_type.updated_at = get_datetime_utc()
        session.add(fee_type)
        audit.record(
            session,
            actor=actor,
            entity_type="order_fee_type",
            entity_id=fee_type.id,
            action="updated",
            changes=changes,
        )
    session.commit()
    session.refresh(fee_type)
    return fee_type


def _apply(
    session: Session, new: dict[str, Any], fields: tuple[str, ...], actor: User
) -> BusinessSettings:
    settings = get_settings(session, for_update=True)
    old = settings.model_dump()
    changes = audit.diff(old, {**old, **new}, fields)
    if changes:
        settings.sqlmodel_update(new)
        settings.updated_at = get_datetime_utc()
        session.add(settings)
        audit.record(
            session,
            actor=actor,
            entity_type="business_settings",
            entity_id=settings.id,
            action="updated",
            changes=changes,
        )
    session.commit()
    session.refresh(settings)
    return settings
