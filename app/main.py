from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status

from app.llm_extraction import (
    InvalidLLMOutputError,
    InvoiceExtractor,
    LLMConfigurationError,
    LLMProviderError,
    LLMTimeoutError,
    get_invoice_extractor,
)
from app.pdf_extraction import (
    NoExtractableTextError,
    PDFExtractionError,
    extract_pdf_text,
)
from app.schemas import Invoice
from app.upload_validation import validate_invoice_pdf

app = FastAPI(title="Extraction Agent", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    """Confirm that the API process is available."""
    return {"status": "ok"}


@app.post("/extractions/invoice", response_model=Invoice)
async def accept_invoice_pdf(
    file: Annotated[UploadFile, File(description="One text-based invoice PDF")],
    extractor: Annotated[InvoiceExtractor, Depends(get_invoice_extractor)],
) -> Invoice:
    """Validate, parse, and extract structured facts from one invoice PDF."""
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

    try:
        return await extractor.extract(extracted.text)
    except LLMConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except LLMTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(exc),
        ) from exc
    except (LLMProviderError, InvalidLLMOutputError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
