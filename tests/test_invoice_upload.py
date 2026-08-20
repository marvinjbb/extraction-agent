from fastapi.testclient import TestClient

from app.main import app
from app.upload_validation import MAX_UPLOAD_SIZE_BYTES
from tests.pdf_factory import build_pdf

client = TestClient(app)


def test_valid_pdf_is_accepted() -> None:
    content = build_pdf("Invoice INV-1001")

    response = client.post(
        "/extractions/invoice",
        files={"file": ("invoice.pdf", content, "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "filename": "invoice.pdf",
        "status": "text_extracted",
        "page_count": 1,
        "text": "Invoice INV-1001",
    }


def test_non_pdf_is_rejected() -> None:
    response = client.post(
        "/extractions/invoice",
        files={"file": ("invoice.txt", b"not a PDF", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json() == {"detail": "Only PDF files are supported."}


def test_empty_pdf_is_rejected() -> None:
    response = client.post(
        "/extractions/invoice",
        files={"file": ("invoice.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "The uploaded PDF is empty."}


def test_oversized_pdf_is_rejected() -> None:
    content = b"%PDF-" + b"0" * MAX_UPLOAD_SIZE_BYTES

    response = client.post(
        "/extractions/invoice",
        files={"file": ("invoice.pdf", content, "application/pdf")},
    )

    assert response.status_code == 413
    assert response.json() == {
        "detail": "The uploaded PDF exceeds the 5 MiB size limit."
    }


def test_file_with_pdf_media_type_but_invalid_signature_is_rejected() -> None:
    response = client.post(
        "/extractions/invoice",
        files={"file": ("invoice.pdf", b"not a PDF", "application/pdf")},
    )

    assert response.status_code == 415
    assert response.json() == {
        "detail": "The uploaded file does not have a valid PDF signature."
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


def test_pdf_without_text_is_rejected_after_upload_validation() -> None:
    response = client.post(
        "/extractions/invoice",
        files={"file": ("invoice.pdf", build_pdf(None), "application/pdf")},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "The uploaded PDF contains no extractable text. "
        "OCR is not supported."
    }
