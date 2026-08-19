from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas import Invoice, LineItem


def test_valid_invoice_data_passes_validation() -> None:
    invoice = Invoice(
        vendor="Acme Supplies",
        invoice_number="INV-1001",
        invoice_date=date(2026, 8, 19),
        currency="USD",
        subtotal=Decimal("100.00"),
        tax=Decimal("8.25"),
        total=Decimal("108.25"),
        line_items=[
            LineItem(
                description="Consulting services",
                quantity=Decimal("2"),
                unit_price=Decimal("50.00"),
                amount=Decimal("100.00"),
            )
        ],
        warnings=["Purchase order number was not present."],
    )

    assert invoice.vendor == "Acme Supplies"
    assert invoice.invoice_date == date(2026, 8, 19)
    assert invoice.total == Decimal("108.25")


def test_missing_invoice_fields_remain_none_or_empty() -> None:
    invoice = Invoice()

    assert invoice.vendor is None
    assert invoice.invoice_number is None
    assert invoice.invoice_date is None
    assert invoice.currency is None
    assert invoice.subtotal is None
    assert invoice.tax is None
    assert invoice.total is None
    assert invoice.line_items == []
    assert invoice.warnings == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("invoice_date", "not-a-date"),
        ("currency", "US"),
        ("total", {"amount": "10.00"}),
        ("warnings", "not-a-list"),
    ],
)
def test_invalid_invoice_field_types_are_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Invoice.model_validate({field: value})


def test_nested_line_items_are_validated_and_converted() -> None:
    invoice = Invoice.model_validate(
        {
            "line_items": [
                {
                    "description": "Hosting",
                    "quantity": "2",
                    "unit_price": "12.50",
                    "amount": "25.00",
                }
            ]
        }
    )

    item = invoice.line_items[0]
    assert isinstance(item, LineItem)
    assert item.quantity == Decimal("2")
    assert item.unit_price == Decimal("12.50")
    assert item.amount == Decimal("25.00")


def test_line_item_requires_a_non_empty_description() -> None:
    with pytest.raises(ValidationError):
        Invoice.model_validate(
            {
                "line_items": [
                    {
                        "description": "   ",
                        "amount": "25.00",
                    }
                ]
            }
        )


def test_unknown_invoice_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Invoice.model_validate({"vendor_name": "Acme Supplies"})
