# Extraction Agent

A production-minded AI engineering portfolio project for extracting validated, structured invoice data from uploaded documents.

## Current Status

Phase 1 is complete locally. The narrow MVP validates one invoice PDF upload, extracts embedded text page by page, asks OpenAI for schema-constrained invoice facts, validates the result with the application-owned Pydantic model, and returns structured JSON. The separate `marvinjb.dev` demo is now connected to this API for local development. Automated tests replace the provider with fakes; controlled live requests have verified the complete browser-to-backend flow.

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

- Git
- Python 3.12 or newer

Clone the repository:

```powershell
git clone https://github.com/marvinjbb/extraction-agent.git
cd extraction-agent
```

Create and activate a virtual environment.

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the application and development dependencies:

```powershell
python -m pip install -e ".[dev]"
```

Create local configuration from the safe example.

PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS/Linux:

```bash
cp .env.example .env
```

Open `.env` locally and set `OPENAI_API_KEY`. Do not paste a real key into `.env.example`, source code, terminal history, issues, or commits. `.env` is ignored by Git. Optional `OPENAI_MODEL` and `OPENAI_TIMEOUT_SECONDS` settings default to `gpt-5.4-nano` and 30 seconds. `FRONTEND_ORIGINS` is a comma-separated CORS allowlist and defaults to the two local port-3000 origins shown in `.env.example`.

Start the local API:

```powershell
python -m uvicorn app.main:app --reload
```

In another terminal, verify health:

```powershell
curl.exe http://127.0.0.1:8000/health
```

On macOS/Linux, use `curl` instead of `curl.exe`. The expected response is:

```json
{"status":"ok"}
```

Run the checks:

```powershell
python -m ruff check .
python -m pytest
python -m pip check
```

Tests use dependency-injected fakes and do not require `OPENAI_API_KEY` or call the real OpenAI API.

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
- Sends extracted text through an isolated OpenAI Structured Outputs adapter.
- Validates provider output against the `Invoice` Pydantic schema.

A valid upload returns structured invoice JSON:

```powershell
curl.exe -X POST http://127.0.0.1:8000/extractions/invoice `
  -F "file=@C:\path\to\invoice.pdf;type=application/pdf"
```

macOS/Linux:

```bash
curl -X POST http://127.0.0.1:8000/extractions/invoice \
  -F "file=@/path/to/invoice.pdf;type=application/pdf"
```

```json
{
  "vendor": "Acme Supplies",
  "invoice_number": "INV-1001",
  "invoice_date": "2026-08-20",
  "currency": "USD",
  "subtotal": "100.00",
  "tax": "8.25",
  "total": "108.25",
  "line_items": [],
  "warnings": []
}
```

## Invoice Schema

`app/schemas.py` defines the extraction result independently from the provider.

An invoice can contain:

- Vendor, invoice number, invoice date, and three-letter uppercase currency code.
- Subtotal, tax, and total as exact decimal values.
- Line items with a required description and optional quantity, unit price, and amount.
- Warnings describing missing or uncertain source information.

Invoice facts are nullable because real documents can omit them. Missing collections default to empty lists. Unknown fields and invalid values are rejected, and no placeholder values are generated.

## LLM Boundary

`app/llm_extraction.py` contains the provider-specific adapter. The FastAPI route depends on the application-owned `InvoiceExtractor` interface rather than OpenAI SDK calls directly. Provider timeouts return HTTP 504; provider and invalid structured-output failures return HTTP 502; missing server configuration returns HTTP 503. Error responses do not expose credentials or provider internals.

The current model default is `gpt-5.4-nano`, selected for this bounded, cost-sensitive data-extraction MVP. Model quality must be evaluated against representative invoices before public deployment.

## Error Responses

Errors use FastAPI's `{"detail":"..."}` shape.

| Status | Meaning |
| --- | --- |
| 400 | The uploaded PDF is empty. |
| 413 | The upload exceeds the 5 MiB limit. |
| 415 | The declared type or file signature is not supported. |
| 422 | The PDF is unreadable or has no extractable embedded text. |
| 502 | The provider failed or returned invalid structured output. |
| 503 | The server has no usable provider configuration. |
| 504 | The provider exceeded its configured timeout. |

## Current Limitations

- Only one text-based PDF is accepted per request; images and OCR are unsupported.
- PDF text order can differ from visual layout, especially for complex tables.
- Schema-valid output can still contain extraction mistakes or conservative omissions.
- Ambiguous labels may be returned as null with warnings rather than inferred.
- Files are processed ephemerally; there is no history, persistence, or retry queue.
- The local MVP has no authentication, public-demo rate limiting, Docker, or deployment configuration yet.
