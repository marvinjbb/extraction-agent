from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile, status

from app.pdf_extraction import (
    NoExtractableTextError,
    PDFExtractionError,
    extract_pdf_text,
)
from app.upload_validation import validate_invoice_pdf

app = FastAPI(title="Extraction Agent", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    """Confirm that the API process is available."""
    return {"status": "ok"}


@app.post("/extractions/invoice")
async def accept_invoice_pdf(
    file: Annotated[UploadFile, File(description="One text-based invoice PDF")],
) -> dict[str, str | int]:
    """Validate an invoice PDF and return its embedded text temporarily."""
    content = await validate_invoice_pdf(file)

    try:
        extracted = extract_pdf_text(content)
    except NoExtractableTextError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except PDFExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return {
        "filename": file.filename or "unnamed.pdf",
        "status": "text_extracted",
        "page_count": extracted.page_count,
        "text": extracted.text,
    }
