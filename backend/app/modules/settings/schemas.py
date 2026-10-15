from datetime import datetime
from decimal import Decimal
from zoneinfo import available_timezones

from pydantic import field_validator
from sqlmodel import Field, SQLModel

from app.modules.settings.models import Language

# Amounts are stored as Numeric(18, 2) VND; other currencies are not supported yet.
SUPPORTED_CURRENCIES = ("VND",)


class BusinessSettingsPublic(SQLModel):
    business_name: str
    currency_code: str
    timezone: str
    allow_negative_stock: bool
    tax_rate: Decimal
    language: Language
    updated_at: datetime


class LanguageUpdate(SQLModel):
    language: Language


class BusinessSettingsUpdate(SQLModel):
    business_name: str = Field(min_length=1, max_length=255)
    currency_code: str = Field(min_length=3, max_length=3)
    timezone: str = Field(min_length=1, max_length=64)
    allow_negative_stock: bool
    tax_rate: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)

    @field_validator("tax_rate")
    @classmethod
    def scale_tax_rate(cls, value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"))

    @field_validator("business_name")
    @classmethod
    def strip_business_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Business name must not be blank")
        return value

    @field_validator("currency_code")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        value = value.upper()
        if value not in SUPPORTED_CURRENCIES:
            raise ValueError(
                f"Unsupported currency; supported: {', '.join(SUPPORTED_CURRENCIES)}"
            )
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        if value not in available_timezones():
            raise ValueError("Timezone must be a valid IANA timezone name")
        return value
