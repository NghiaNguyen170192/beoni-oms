from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, SessionDep
from app.models import User
from app.modules.identity.dependencies import require_permission
from app.modules.identity.permissions import Permission
from app.modules.settings import service
from app.modules.settings.dependencies import BusinessSettingsDep
from app.modules.settings.models import BusinessSettings
from app.modules.settings.schemas import (
    BusinessSettingsPublic,
    BusinessSettingsUpdate,
    LanguageUpdate,
)

router = APIRouter(prefix="/settings", tags=["settings"])


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
    actor: Annotated[User, Depends(require_permission(Permission.SETTINGS_MANAGE))],
) -> BusinessSettings:
    """
    Update business settings. Owner only; every change is audited.
    """
    return service.update_settings(session, settings_in=settings_in, actor=actor)


@router.put("/business/language", response_model=BusinessSettingsPublic)
def update_language(
    session: SessionDep,
    language_in: LanguageUpdate,
    actor: Annotated[User, Depends(require_permission(Permission.SETTINGS_MANAGE))],
) -> BusinessSettings:
    """
    Set the interface language for every user. Owner only; audited.
    """
    return service.update_language(session, language_in=language_in, actor=actor)
