from fastapi import HTTPException, UploadFile, status

PDF_CONTENT_TYPE = "application/pdf"
PDF_SIGNATURE = b"%PDF-"
MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024


async def validate_invoice_pdf(file: UploadFile) -> bytes:
    """Validate an invoice PDF upload and return its bounded contents."""
    if file.content_type != PDF_CONTENT_TYPE:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF files are supported.",
        )

    content = await file.read(MAX_UPLOAD_SIZE_BYTES + 1)

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded PDF is empty.",
        )

    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="The uploaded PDF exceeds the 5 MiB size limit.",
        )

    if not content.startswith(PDF_SIGNATURE):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="The uploaded file does not have a valid PDF signature.",
        )

    return content
