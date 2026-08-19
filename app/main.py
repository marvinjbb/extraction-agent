from typing import Annotated

from fastapi import FastAPI, File, UploadFile

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
    """Accept one validated invoice PDF without processing its contents yet."""
    size_bytes = await validate_invoice_pdf(file)

    return {
        "filename": file.filename or "unnamed.pdf",
        "content_type": file.content_type or "application/octet-stream",
        "size_bytes": size_bytes,
        "status": "accepted",
    }
