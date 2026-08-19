from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
FiniteDecimal = Annotated[Decimal, Field(allow_inf_nan=False)]


class LineItem(BaseModel):
    """One invoice line item with only its description required."""

    model_config = ConfigDict(extra="forbid")

    description: NonEmptyString
    quantity: FiniteDecimal | None = None
    unit_price: FiniteDecimal | None = None
    amount: FiniteDecimal | None = None


class Invoice(BaseModel):
    """Structured invoice facts extracted from a document."""

    model_config = ConfigDict(extra="forbid")

    vendor: NonEmptyString | None = None
    invoice_number: NonEmptyString | None = None
    invoice_date: date | None = None
    currency: CurrencyCode | None = None
    subtotal: FiniteDecimal | None = None
    tax: FiniteDecimal | None = None
    total: FiniteDecimal | None = None
    line_items: list[LineItem] = Field(default_factory=list)
    warnings: list[NonEmptyString] = Field(default_factory=list)
