import uuid
from datetime import datetime
from decimal import Decimal
from zoneinfo import available_timezones

from pydantic import field_validator, model_validator
from sqlmodel import Field, SQLModel
from typing_extensions import Self

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


class BusinessNameUpdate(SQLModel):
    business_name: str = Field(min_length=1, max_length=255)

    @field_validator("business_name")
    @classmethod
    def strip_business_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Business name must not be blank")
        return value


class BusinessSettingsUpdate(SQLModel):
    currency_code: str = Field(min_length=3, max_length=3)
    timezone: str = Field(min_length=1, max_length=64)
    allow_negative_stock: bool

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


class BusinessTaxRateUpdate(SQLModel):
    tax_rate: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)

    @field_validator("tax_rate")
    @classmethod
    def scale_tax_rate(cls, value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"))


def _clean_fee_name(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError("Fee name must not be blank")
    return value


class OrderFeeTypeCreate(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    is_enabled: bool = True

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _clean_fee_name(value) or ""


class OrderFeeTypeUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=255)
    is_enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("name must not be null")
        return _clean_fee_name(value)

    @field_validator("is_enabled")
    @classmethod
    def require_enabled_value(cls, value: bool | None) -> bool:
        if value is None:
            raise ValueError("is_enabled must be true or false")
        return value

    @model_validator(mode="after")
    def ensure_at_least_one_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one fee field must be provided")
        return self


class OrderFeeTypePublic(SQLModel):
    id: uuid.UUID
    name: str
    is_enabled: bool
    updated_at: datetime
