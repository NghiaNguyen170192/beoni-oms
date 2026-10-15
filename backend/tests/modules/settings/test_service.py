from sqlmodel import Session, delete

from app.modules.settings import service
from app.modules.settings.models import BusinessSettings


def test_defaults_when_no_settings_row(db: Session) -> None:
    db.exec(delete(BusinessSettings))  # type: ignore[call-overload]

    settings = service.get_settings(db)

    assert settings.currency_code == "VND"
    assert settings.timezone == "Asia/Ho_Chi_Minh"
    assert settings.allow_negative_stock is False
    assert settings.business_name


def test_settings_is_a_singleton(db: Session) -> None:
    first = service.get_settings(db)
    second = service.get_settings(db)

    assert first.id == second.id == 1
