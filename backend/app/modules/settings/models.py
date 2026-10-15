from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import CheckConstraint, DateTime, Numeric
from sqlmodel import Field, SQLModel

from app.core.db_types import EnumString
from app.models import get_datetime_utc

SETTINGS_ID = 1
DEFAULT_BUSINESS_NAME = "Beoni"
DEFAULT_CURRENCY_CODE = "VND"
DEFAULT_TIMEZONE = "Asia/Ho_Chi_Minh"


class Language(str, Enum):
    EN = "en"
    VI = "vi"


LANGUAGE_VALUES_SQL = ", ".join(f"'{language.value}'" for language in Language)


class BusinessSettings(SQLModel, table=True):
    """Singleton row (id = 1), seeded by migration."""

    __tablename__ = "business_settings"
    __table_args__ = (
        CheckConstraint(f"id = {SETTINGS_ID}", name="ck_business_settings_singleton"),
        CheckConstraint(
            "tax_rate >= 0 AND tax_rate <= 100", name="ck_business_settings_tax_rate"
        ),
        CheckConstraint(
            f"language IN ({LANGUAGE_VALUES_SQL})",
            name="ck_business_settings_language",
        ),
    )

    id: int = Field(
        default=SETTINGS_ID,
        primary_key=True,
        sa_column_kwargs={"autoincrement": False},
    )
    business_name: str = Field(default=DEFAULT_BUSINESS_NAME, max_length=255)
    currency_code: str = Field(default=DEFAULT_CURRENCY_CODE, max_length=3)
    timezone: str = Field(default=DEFAULT_TIMEZONE, max_length=64)
    allow_negative_stock: bool = False
    # Percent included in menu prices (prices are tax-inclusive).
    tax_rate: Decimal = Field(default=Decimal("0"), sa_type=Numeric(5, 2))  # type: ignore
    # Interface language for every user.
    language: Language = Field(
        default=Language.EN,
        sa_type=EnumString(Language, length=2),  # type: ignore
        nullable=False,
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        nullable=False,
    )
