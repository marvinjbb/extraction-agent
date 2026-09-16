from io import BytesIO

import pytest
from pypdf import PdfWriter

from app.pdf_extraction import (
    NoExtractableTextError,
    PDFExtractionError,
    extract_pdf_text,
)
from tests.pdf_factory import build_pdf


def test_text_based_pdf_extracts_text() -> None:
    result = extract_pdf_text(build_pdf("Invoice INV-1001"))

    assert result.page_count == 1
    assert result.text == "Invoice INV-1001"


def test_multi_page_pdf_combines_text_in_page_order() -> None:
    result = extract_pdf_text(build_pdf("First page", "Second page"))

    assert result.page_count == 2
    assert result.text == "First page\n\nSecond page"


def test_malformed_pdf_is_rejected_cleanly() -> None:
    with pytest.raises(PDFExtractionError, match="could not be read"):
        extract_pdf_text(b"%PDF-1.4\nthis is not a complete PDF")


def test_pdf_without_extractable_text_is_rejected_clearly() -> None:
    with pytest.raises(NoExtractableTextError, match="no extractable text"):
        extract_pdf_text(build_pdf(None))


def test_password_protected_pdf_is_rejected() -> None:
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("demo-password")
    writer.write(output)

    with pytest.raises(PDFExtractionError, match="Password-protected"):
        extract_pdf_text(output.getvalue())
