import os
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from app.invoice_query import InvoiceQueryService, get_invoice_query_service
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
from app.schemas import Invoice, InvoiceQueryRequest, InvoiceQueryResponse
from app.upload_validation import validate_invoice_pdf

load_dotenv()

DEFAULT_FRONTEND_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


def get_frontend_origins() -> list[str]:
    """Return explicit browser origins allowed to call this local API."""
    configured = os.getenv("FRONTEND_ORIGINS")
    if configured is None:
        return list(DEFAULT_FRONTEND_ORIGINS)
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


app = FastAPI(title="Extraction Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_frontend_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Accept", "Content-Type"],
)


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


@app.post("/extractions/invoice/query", response_model=InvoiceQueryResponse)
async def query_invoice(
    request: InvoiceQueryRequest,
    query_service: Annotated[
        InvoiceQueryService, Depends(get_invoice_query_service)
    ],
) -> InvoiceQueryResponse:
    """Answer one question using only an already-validated invoice."""
    try:
        answer = await query_service.answer(request.question, request.invoice)
        return InvoiceQueryResponse(answer=answer)
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
