from dataclasses import dataclass
from enum import StrEnum

from fastapi import HTTPException, UploadFile, status

from app.observability import log_event

PDF_CONTENT_TYPE = "application/pdf"
PDF_SIGNATURE = b"%PDF-"
JPEG_CONTENT_TYPES = {"image/jpeg", "image/jpg"}
PNG_CONTENT_TYPE = "image/png"
JPEG_SIGNATURE = b"\xff\xd8\xff"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024


class InvoiceMediaType(StrEnum):
    PDF = "application/pdf"
    JPEG = "image/jpeg"
    PNG = "image/png"


@dataclass(frozen=True)
class ValidatedInvoiceUpload:
    content: bytes
    media_type: InvoiceMediaType


async def validate_invoice_upload(file: UploadFile) -> ValidatedInvoiceUpload:
    """Validate one supported invoice upload and return its bounded contents."""
    media_type = _normalized_media_type(file.content_type)
    if media_type is None:
        log_event(
            "upload_validation_failed",
            outcome="rejected",
            error_category="unsupported_media_type",
        )
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF, JPG, JPEG, and PNG invoice files are supported.",
        )

    content = await file.read(MAX_UPLOAD_SIZE_BYTES + 1)

    if not content:
        log_event(
            "upload_validation_failed",
            outcome="rejected",
            error_category="empty_upload",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded invoice file is empty.",
        )

    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        log_event(
            "upload_validation_failed",
            outcome="rejected",
            error_category="upload_too_large",
            size_bucket="over_5_mib",
        )
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="The uploaded invoice file exceeds the 5 MiB size limit.",
        )

    expected_signature = {
        InvoiceMediaType.PDF: PDF_SIGNATURE,
        InvoiceMediaType.JPEG: JPEG_SIGNATURE,
        InvoiceMediaType.PNG: PNG_SIGNATURE,
    }[media_type]
    if not content.startswith(expected_signature):
        log_event(
            "upload_validation_failed",
            outcome="rejected",
            error_category="signature_mismatch",
            media_type=media_type.value,
        )
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="The uploaded file content does not match its declared format.",
        )

    log_event(
        "upload_validated",
        outcome="success",
        media_type=media_type.value,
        size_bucket=_size_bucket(len(content)),
    )
    return ValidatedInvoiceUpload(content=content, media_type=media_type)


def _normalized_media_type(content_type: str | None) -> InvoiceMediaType | None:
    if content_type == PDF_CONTENT_TYPE:
        return InvoiceMediaType.PDF
    if content_type in JPEG_CONTENT_TYPES:
        return InvoiceMediaType.JPEG
    if content_type == PNG_CONTENT_TYPE:
        return InvoiceMediaType.PNG
    return None


def _size_bucket(size: int) -> str:
    if size < 100 * 1024:
        return "under_100_kib"
    if size < 1024 * 1024:
        return "100_kib_to_1_mib"
    return "1_mib_to_5_mib"


async def validate_invoice_pdf(file: UploadFile) -> bytes:
    """Backward-compatible PDF-only validation helper."""
    upload = await validate_invoice_upload(file)
    if upload.media_type is not InvoiceMediaType.PDF:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF files are supported.",
        )
    return upload.content
