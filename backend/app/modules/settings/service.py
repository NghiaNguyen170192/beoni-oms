from typing import Any

from sqlmodel import Session

from app.models import User, get_datetime_utc
from app.modules.audit import service as audit
from app.modules.settings.models import SETTINGS_ID, BusinessSettings
from app.modules.settings.schemas import BusinessSettingsUpdate, LanguageUpdate

_AUDITED_FIELDS = (
    "business_name",
    "currency_code",
    "timezone",
    "allow_negative_stock",
    "tax_rate",
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


def update_language(
    session: Session, *, language_in: LanguageUpdate, actor: User
) -> BusinessSettings:
    return _apply(session, language_in.model_dump(), ("language",), actor)


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
