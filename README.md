# Extraction Agent

A production-minded AI engineering portfolio project for extracting validated, structured invoice data from uploaded documents.

## Current Status

Phase 1D is complete locally. The FastAPI application validates one invoice PDF upload and extracts embedded text page by page. Pydantic models independently define the future structured invoice output. LLM extraction has not been implemented.

## Approved MVP

The first local MVP will accept one text-based invoice PDF, extract its text, use an LLM to produce structured invoice fields, validate the output, and return JSON.

Initial fields:

- Vendor
- Invoice number
- Invoice date
- Currency
- Subtotal, tax, and total when present
- Line items
- Warnings or nullable fields for missing/uncertain data

Image uploads, OCR, multiple document types, persistence, Docker, and deployment are intentionally outside the first MVP.

## Platform Context

The future React interface will live in the separate `marvinjb.dev` portfolio repository at `marvinjb.dev/demo/extraction`. This repository will provide the backend API. In production, the portfolio will call an extraction route under `https://api.marvinjb.dev`, which will be routed through Nginx to this service's Docker container on the shared Ubuntu VPS.

## Documentation

- `AGENTS.md` — Governing project instructions and scope.
- `docs/ARCHITECTURE.md` — Current and target technical architecture.
- `docs/ROADMAP.md` — Living phased implementation tracker.
- `docs/DECISIONS.md` — Architecture Decision Record log.

Setup, API, testing, deployment, security, and observability instructions will be added as those capabilities are actually designed and implemented.

## Local Development

Requirements:

- Python 3.12 or newer

Create and activate a virtual environment in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the application and development dependencies:

```powershell
python -m pip install -e ".[dev]"
```

Start the local API:

```powershell
python -m uvicorn app.main:app --reload
```

Then open `http://127.0.0.1:8000/health`. The expected response is:

```json
{"status":"ok"}
```

Run the checks:

```powershell
python -m ruff check .
python -m pytest
```

## Current API

### `GET /health`

Confirms that the API process is available.

### `POST /extractions/invoice`

Accepts one multipart upload in the `file` field. The current validation layer:

- Accepts only `application/pdf` uploads with a `%PDF-` file signature.
- Rejects empty files.
- Rejects files larger than 5 MiB (5,242,880 bytes).
- Extracts embedded text with `pypdf`; it does not persist the PDF.
- Rejects malformed PDFs and PDFs without extractable text.
- Does not perform OCR.

A valid upload currently returns a temporary development response:

```json
{
  "filename": "invoice.pdf",
  "status": "text_extracted",
  "page_count": 1,
  "text": "Invoice INV-1001"
}
```

This response will be replaced by structured invoice extraction in Phase 1E.

## Invoice Schema

`app/schemas.py` defines the future extraction result independently from the current upload response.

An invoice can contain:

- Vendor, invoice number, invoice date, and three-letter uppercase currency code.
- Subtotal, tax, and total as exact decimal values.
- Line items with a required description and optional quantity, unit price, and amount.
- Warnings describing missing or uncertain source information.

Invoice facts are nullable because real documents can omit them. Missing collections default to empty lists. Unknown fields and invalid values are rejected, and no placeholder values are generated.
