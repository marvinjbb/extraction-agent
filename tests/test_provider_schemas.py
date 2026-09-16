from datetime import date
from decimal import Decimal

import pytest

from app.provider_schemas import (
    ProviderInvoice,
    ProviderInvoiceConversionError,
    ProviderLineItem,
    parse_provider_decimal,
    provider_invoice_to_domain,
)
from app.schemas import Invoice


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0", Decimal("0")),
        ("12", Decimal("12")),
        ("12.50", Decimal("12.50")),
        ("-4.25", Decimal("-4.25")),
        ("0.001", Decimal("0.001")),
        (None, None),
    ],
)
def test_provider_decimal_conversion_preserves_exact_decimal_semantics(
    raw: str | None, expected: Decimal | None
) -> None:
    converted = parse_provider_decimal(raw)

    assert converted == expected
    if raw is not None:
        assert converted is not None
        assert converted.as_tuple() == Decimal(raw).as_tuple()


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "N/A",
        "$12",
        "$12.00",
        "1,234.56",
        "12 USD",
        "NaN",
        "Infinity",
        "-Infinity",
    ],
)
def test_provider_decimal_conversion_rejects_non_plain_or_nonfinite_values(
    raw: str,
) -> None:
    with pytest.raises(ProviderInvoiceConversionError):
        parse_provider_decimal(raw)


def test_complete_provider_invoice_converts_to_domain_invoice() -> None:
    provider_invoice = ProviderInvoice(
        vendor="Acme Supplies",
        invoice_number="INV-1001",
        invoice_date=date(2026, 8, 20),
        currency="USD",
        subtotal="100.00",
        tax="8.25",
        total="108.25",
        line_items=[
            ProviderLineItem(
                description="Consulting",
                quantity="2",
                unit_price="50.00",
                amount="100.00",
            )
        ],
        warnings=["Purchase order number was not present."],
    )

    invoice = provider_invoice_to_domain(provider_invoice)

    assert isinstance(invoice, Invoice)
    assert invoice.subtotal == Decimal("100.00")
    assert invoice.tax == Decimal("8.25")
    assert invoice.total == Decimal("108.25")
    assert invoice.line_items[0].quantity == Decimal("2")
    assert invoice.line_items[0].unit_price == Decimal("50.00")
    assert invoice.line_items[0].amount == Decimal("100.00")


def test_invalid_top_level_provider_money_fails_closed() -> None:
    provider_invoice = ProviderInvoice.model_construct(
        subtotal="$12.00", line_items=[], warnings=[]
    )

    with pytest.raises(ProviderInvoiceConversionError):
        provider_invoice_to_domain(provider_invoice)


def test_invalid_line_item_provider_money_fails_closed() -> None:
    item = ProviderLineItem.model_construct(
        description="Consulting",
        quantity="1",
        unit_price="1,234.56",
        amount="1234.56",
    )
    provider_invoice = ProviderInvoice.model_construct(line_items=[item], warnings=[])

    with pytest.raises(ProviderInvoiceConversionError):
        provider_invoice_to_domain(provider_invoice)


def test_domain_validation_remains_authoritative_after_provider_conversion() -> None:
    provider_invoice = ProviderInvoice.model_construct(
        currency="US", line_items=[], warnings=[]
    )

    with pytest.raises(ProviderInvoiceConversionError):
        provider_invoice_to_domain(provider_invoice)
