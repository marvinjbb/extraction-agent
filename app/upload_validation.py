from dataclasses import dataclass
from enum import StrEnum

from fastapi import HTTPException, UploadFile, status

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
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF, JPG, JPEG, and PNG invoice files are supported.",
        )

    content = await file.read(MAX_UPLOAD_SIZE_BYTES + 1)

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded invoice file is empty.",
        )

    if len(content) > MAX_UPLOAD_SIZE_BYTES:
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
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="The uploaded file content does not match its declared format.",
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


async def validate_invoice_pdf(file: UploadFile) -> bytes:
    """Backward-compatible PDF-only validation helper."""
    upload = await validate_invoice_upload(file)
    if upload.media_type is not InvoiceMediaType.PDF:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF files are supported.",
        )
    return upload.content
