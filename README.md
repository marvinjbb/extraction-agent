# Extraction Agent

A production-minded AI engineering portfolio project for extracting validated, structured invoice data from uploaded documents.

## Current Status

Phase 1B is complete locally. The FastAPI application accepts and validates one invoice PDF upload. PDF text parsing and document extraction have not been implemented.

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
- Reads the upload only for validation; it does not parse or persist the PDF.

A valid upload currently returns temporary acceptance metadata:

```json
{
  "filename": "invoice.pdf",
  "content_type": "application/pdf",
  "size_bytes": 12345,
  "status": "accepted"
}
```
