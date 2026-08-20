from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.llm_extraction import get_invoice_extractor
from app.main import app
from app.schemas import Invoice, LineItem
from tests.pdf_factory import build_pdf

client = TestClient(app)


class RecordingExtractor:
    def __init__(self, result: Invoice) -> None:
        self.result = result
        self.received_text: str | None = None

    async def extract(self, document_text: str) -> Invoice:
        self.received_text = document_text
        return self.result


@pytest.mark.parametrize(
    ("pages", "invoice", "expected_text"),
    [
        (
            ("Acme Supplies INV-1001 USD 108.25",),
            Invoice(
                vendor="Acme Supplies",
                invoice_number="INV-1001",
                invoice_date=date(2026, 8, 20),
                currency="USD",
                subtotal=Decimal("100.00"),
                tax=Decimal("8.25"),
                total=Decimal("108.25"),
                line_items=[
                    LineItem(
                        description="Consulting",
                        quantity=Decimal("2"),
                        unit_price=Decimal("50.00"),
                        amount=Decimal("100.00"),
                    )
                ],
            ),
            "Acme Supplies INV-1001 USD 108.25",
        ),
        (
            ("Northwind GmbH RE-77 EUR", "Total 49.90; tax not shown"),
            Invoice(
                vendor="Northwind GmbH",
                invoice_number="RE-77",
                currency="EUR",
                total=Decimal("49.90"),
                warnings=["Invoice date and tax were not present."],
            ),
            "Northwind GmbH RE-77 EUR\n\nTotal 49.90; tax not shown",
        ),
        (
            ("Freelance services receipt total GBP 250.00",),
            Invoice(
                currency="GBP",
                total=Decimal("250.00"),
                warnings=["Vendor, invoice number, and invoice date were not present."],
            ),
            "Freelance services receipt total GBP 250.00",
        ),
    ],
)
def test_representative_invoice_pdfs_complete_the_local_pipeline(
    pages: tuple[str, ...],
    invoice: Invoice,
    expected_text: str,
) -> None:
    extractor = RecordingExtractor(invoice)
    app.dependency_overrides[get_invoice_extractor] = lambda: extractor

    try:
        response = client.post(
            "/extractions/invoice",
            files={"file": ("invoice.pdf", build_pdf(*pages), "application/pdf")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert Invoice.model_validate(response.json()) == invoice
    assert extractor.received_text == expected_text
