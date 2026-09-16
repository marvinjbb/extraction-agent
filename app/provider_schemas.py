"""Provider-facing invoice contracts and the domain conversion boundary."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from app.schemas import CurrencyCode, Invoice, NonEmptyString

PROVIDER_DECIMAL_PATTERN = r"^-?[0-9]+(\.[0-9]+)?$"
PROVIDER_DECIMAL_DESCRIPTION = (
    "Plain decimal value without currency symbols or thousands separators."
)
_PROVIDER_DECIMAL_RE = re.compile(PROVIDER_DECIMAL_PATTERN)

ProviderDecimalString = Annotated[
    str,
    StringConstraints(pattern=PROVIDER_DECIMAL_PATTERN),
    Field(description=PROVIDER_DECIMAL_DESCRIPTION),
]


class ProviderLineItem(BaseModel):
    """Strict line-item shape sent to and parsed from the LLM provider."""

    model_config = ConfigDict(extra="forbid")

    description: NonEmptyString
    quantity: ProviderDecimalString | None = None
    unit_price: ProviderDecimalString | None = None
    amount: ProviderDecimalString | None = None


class ProviderInvoice(BaseModel):
    """Strict provider DTO that avoids exposing Python Decimal JSON Schema."""

    model_config = ConfigDict(extra="forbid")

    vendor: NonEmptyString | None = None
    invoice_number: NonEmptyString | None = None
    invoice_date: date | None = None
    currency: CurrencyCode | None = None
    subtotal: ProviderDecimalString | None = None
    tax: ProviderDecimalString | None = None
    total: ProviderDecimalString | None = None
    line_items: list[ProviderLineItem] = Field(default_factory=list)
    warnings: list[NonEmptyString] = Field(default_factory=list)


class ProviderInvoiceConversionError(ValueError):
    """Raised when provider data cannot become a valid domain Invoice."""


def parse_provider_decimal(value: str | None) -> Decimal | None:
    """Convert one exact plain-decimal string without normalization or floats."""
    if value is None:
        return None
    if _PROVIDER_DECIMAL_RE.fullmatch(value) is None:
        raise ProviderInvoiceConversionError("Invalid provider decimal string.")
    try:
        converted = Decimal(value)
    except InvalidOperation as exc:
        raise ProviderInvoiceConversionError(
            "Invalid provider decimal string."
        ) from exc
    if not converted.is_finite():
        raise ProviderInvoiceConversionError("Provider decimal must be finite.")
    return converted


def provider_invoice_to_domain(provider_invoice: ProviderInvoice) -> Invoice:
    """Convert one provider DTO and revalidate it as the domain Invoice."""
    data = provider_invoice.model_dump()
    for name in ("subtotal", "tax", "total"):
        data[name] = parse_provider_decimal(data[name])

    converted_items: list[dict[str, object]] = []
    for item in provider_invoice.line_items:
        item_data = item.model_dump()
        for name in ("quantity", "unit_price", "amount"):
            item_data[name] = parse_provider_decimal(item_data[name])
        converted_items.append(item_data)
    data["line_items"] = converted_items

    try:
        return Invoice.model_validate(data)
    except ValidationError as exc:
        raise ProviderInvoiceConversionError(
            "Provider invoice did not satisfy the domain contract."
        ) from exc
