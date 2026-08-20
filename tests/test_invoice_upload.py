from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.llm_extraction import (
    InvalidLLMOutputError,
    LLMConfigurationError,
    LLMProviderError,
    LLMTimeoutError,
    get_invoice_extractor,
    get_vision_invoice_extractor,
)
from app.main import app
from app.schemas import Invoice, LineItem
from app.upload_validation import MAX_UPLOAD_SIZE_BYTES
from tests.pdf_factory import build_pdf

client = TestClient(app)


class FakeInvoiceExtractor:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.received_text: str | None = None
        self.received_images = None

    async def extract(self, document_text: str) -> Invoice:
        self.received_text = document_text
        if self.error:
            raise self.error
        return Invoice(
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
                    quantity=Decimal("1"),
                    unit_price=Decimal("100.00"),
                    amount=Decimal("100.00"),
                )
            ],
        )

    async def extract_images(self, images) -> Invoice:
        self.received_images = images
        return await self.extract("vision input")


@pytest.fixture(autouse=True)
def use_fake_invoice_extractor() -> FakeInvoiceExtractor:
    extractor = FakeInvoiceExtractor()
    app.dependency_overrides[get_invoice_extractor] = lambda: extractor
    app.dependency_overrides[get_vision_invoice_extractor] = lambda: extractor
    yield extractor
    app.dependency_overrides.clear()


def test_valid_pdf_returns_structured_invoice(
    use_fake_invoice_extractor: FakeInvoiceExtractor,
) -> None:
    content = build_pdf("Invoice INV-1001")

    response = client.post(
        "/extractions/invoice",
        files={"file": ("invoice.pdf", content, "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "vendor": "Acme Supplies",
        "invoice_number": "INV-1001",
        "invoice_date": "2026-08-20",
        "currency": "USD",
        "subtotal": "100.00",
        "tax": "8.25",
        "total": "108.25",
        "line_items": [
            {
                "description": "Consulting",
                "quantity": "1",
                "unit_price": "100.00",
                "amount": "100.00",
            }
        ],
        "warnings": [],
    }
    assert use_fake_invoice_extractor.received_text == "Invoice INV-1001"


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (
            LLMConfigurationError("provider is not configured"),
            503,
            "provider is not configured",
        ),
        (LLMTimeoutError("provider timed out"), 504, "provider timed out"),
        (LLMProviderError("provider failed"), 502, "provider failed"),
        (InvalidLLMOutputError("invalid output"), 502, "invalid output"),
    ],
)
def test_llm_failures_return_clear_http_errors(
    error: Exception,
    expected_status: int,
    expected_detail: str,
) -> None:
    app.dependency_overrides[get_invoice_extractor] = lambda: FakeInvoiceExtractor(
        error
    )

    response = client.post(
        "/extractions/invoice",
        files={"file": ("invoice.pdf", build_pdf("Invoice"), "application/pdf")},
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}


def test_non_pdf_is_rejected() -> None:
    response = client.post(
        "/extractions/invoice",
        files={"file": ("invoice.txt", b"not a PDF", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json() == {
        "detail": "Only PDF, JPG, JPEG, and PNG invoice files are supported."
    }


def test_empty_pdf_is_rejected() -> None:
    response = client.post(
        "/extractions/invoice",
        files={"file": ("invoice.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "The uploaded invoice file is empty."}


def test_oversized_pdf_is_rejected() -> None:
    content = b"%PDF-" + b"0" * MAX_UPLOAD_SIZE_BYTES

    response = client.post(
        "/extractions/invoice",
        files={"file": ("invoice.pdf", content, "application/pdf")},
    )

    assert response.status_code == 413
    assert response.json() == {
        "detail": "The uploaded invoice file exceeds the 5 MiB size limit."
    }


def test_file_with_pdf_media_type_but_invalid_signature_is_rejected() -> None:
    response = client.post(
        "/extractions/invoice",
        files={"file": ("invoice.pdf", b"not a PDF", "application/pdf")},
    )

    assert response.status_code == 415
    assert response.json() == {
        "detail": "The uploaded file content does not match its declared format."
    }


def test_malformed_pdf_is_rejected_after_upload_validation() -> None:
    response = client.post(
        "/extractions/invoice",
        files={
            "file": (
                "invoice.pdf",
                b"%PDF-1.4\nthis is not a complete PDF",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "The uploaded PDF could not be read."}


def test_pdf_without_text_uses_vision_fallback(
    use_fake_invoice_extractor: FakeInvoiceExtractor,
) -> None:
    response = client.post(
        "/extractions/invoice",
        files={"file": ("invoice.pdf", build_pdf(None), "application/pdf")},
    )

    assert response.status_code == 200
    assert use_fake_invoice_extractor.received_images is not None
    assert len(use_fake_invoice_extractor.received_images) == 1


@pytest.mark.parametrize(
    ("filename", "content_type", "image_format"),
    [
        ("invoice.jpg", "image/jpeg", "JPEG"),
        ("invoice.jpeg", "image/jpeg", "JPEG"),
        ("invoice.png", "image/png", "PNG"),
    ],
)
def test_supported_image_uses_vision_extraction(
    filename: str,
    content_type: str,
    image_format: str,
    use_fake_invoice_extractor: FakeInvoiceExtractor,
) -> None:
    image = Image.new("RGB", (600, 800), "white")
    content = BytesIO()
    image.save(content, format=image_format)

    response = client.post(
        "/extractions/invoice",
        files={"file": (filename, content.getvalue(), content_type)},
    )

    assert response.status_code == 200
    assert use_fake_invoice_extractor.received_images is not None
    assert len(use_fake_invoice_extractor.received_images) == 1
    assert use_fake_invoice_extractor.received_images[0].media_type == "image/jpeg"


def test_image_with_mismatched_declared_format_is_rejected() -> None:
    image = Image.new("RGB", (20, 20), "white")
    content = BytesIO()
    image.save(content, format="PNG")

    response = client.post(
        "/extractions/invoice",
        files={"file": ("invoice.jpg", content.getvalue(), "image/jpeg")},
    )

    assert response.status_code == 415
    assert response.json() == {
        "detail": "The uploaded file content does not match its declared format."
    }


def test_unreadable_image_is_rejected_cleanly() -> None:
    response = client.post(
        "/extractions/invoice",
        files={"file": ("invoice.jpg", b"\xff\xd8\xffnot-an-image", "image/jpeg")},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "The uploaded image could not be read."}
