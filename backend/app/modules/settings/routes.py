import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, SessionDep
from app.models import User
from app.modules.identity.dependencies import require_permission
from app.modules.identity.permissions import Permission
from app.modules.settings import service
from app.modules.settings.dependencies import BusinessSettingsDep
from app.modules.settings.models import BusinessSettings, OrderFeeType
from app.modules.settings.schemas import (
    BusinessNameUpdate,
    BusinessSettingsPublic,
    BusinessSettingsUpdate,
    BusinessTaxRateUpdate,
    LanguageUpdate,
    OrderFeeTypeCreate,
    OrderFeeTypePublic,
    OrderFeeTypeUpdate,
)

router = APIRouter(prefix="/settings", tags=["settings"])

SettingsManager = Annotated[
    User, Depends(require_permission(Permission.SETTINGS_MANAGE))
]
OrderFeeViewer = Annotated[
    User, Depends(require_permission(Permission.ORDERING_CREATE))
]


@router.get("/business", response_model=BusinessSettingsPublic)
def read_business_settings(
    _current_user: CurrentUser, settings: BusinessSettingsDep
) -> BusinessSettings:
    """
    Business-wide settings (currency, timezone, stock policy).
    """
    return settings


@router.put("/business", response_model=BusinessSettingsPublic)
def update_business_settings(
    session: SessionDep,
    settings_in: BusinessSettingsUpdate,
    actor: SettingsManager,
) -> BusinessSettings:
    """
    Update business settings. Owner only; every change is audited.
    """
    return service.update_settings(session, settings_in=settings_in, actor=actor)


@router.put("/business/tax-rate", response_model=BusinessSettingsPublic)
def update_business_tax_rate(
    session: SessionDep, rate_in: BusinessTaxRateUpdate, actor: SettingsManager
) -> BusinessSettings:
    return service.update_tax_rate(
        session, tax_rate=rate_in.tax_rate, actor=actor
    )


@router.put("/business/name", response_model=BusinessSettingsPublic)
def update_business_name(
    session: SessionDep, name_in: BusinessNameUpdate, actor: SettingsManager
) -> BusinessSettings:
    return service.update_business_name(session, name_in=name_in, actor=actor)


@router.put("/business/language", response_model=BusinessSettingsPublic)
def update_language(
    session: SessionDep,
    language_in: LanguageUpdate,
    actor: SettingsManager,
) -> BusinessSettings:
    """
    Set the interface language for every user. Owner only; audited.
    """
    return service.update_language(session, language_in=language_in, actor=actor)


@router.get("/order-fees", response_model=list[OrderFeeTypePublic])
def read_order_fee_types(
    session: SessionDep, _actor: OrderFeeViewer
) -> list[OrderFeeType]:
    return service.list_order_fee_types(session)


@router.get("/order-fees/admin", response_model=list[OrderFeeTypePublic])
def read_all_order_fee_types(
    session: SessionDep, _actor: SettingsManager
) -> list[OrderFeeType]:
    return service.list_order_fee_types(session, include_disabled=True)


@router.post(
    "/order-fees", response_model=OrderFeeTypePublic, status_code=201
)
def create_order_fee_type(
    session: SessionDep, data: OrderFeeTypeCreate, actor: SettingsManager
) -> OrderFeeType:
    return service.create_order_fee_type(session, data=data, actor=actor)


@router.patch(
    "/order-fees/{fee_type_id}", response_model=OrderFeeTypePublic
)
def update_order_fee_type(
    session: SessionDep,
    fee_type_id: uuid.UUID,
    data: OrderFeeTypeUpdate,
    actor: SettingsManager,
) -> OrderFeeType:
    return service.update_order_fee_type(
        session, fee_type_id=fee_type_id, data=data, actor=actor
    )
