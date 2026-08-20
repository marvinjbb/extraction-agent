# Extraction Agent

A production-minded AI engineering portfolio project for extracting validated, structured invoice data from uploaded documents.

## Current Status

Phase 3.6 extends the complete local MVP to text PDFs, scanned/image-only PDFs, JPG/JPEG, and PNG invoices. Readable PDFs retain the efficient `pypdf` text path; scanned PDFs and images use a bounded OpenAI vision path. Both routes return the same application-owned Pydantic `Invoice` model. The separate `marvinjb.dev` demo is connected to this API for local development. Automated tests replace the provider with fakes.

Phase 3.5 adds stateless **Ask This Invoice** queries. `POST /extractions/invoice/query` accepts one question plus the existing `Invoice` JSON and returns `{"answer":"..."}`. It never receives the original PDF, previous messages, frontend prompts, provider settings, or credentials.

Phase 4 packages the unchanged backend as a non-root Docker container based on Python 3.12 slim. The image contains runtime dependencies only, exposes port 8000, reads configuration at container start, and includes a lightweight `/health` check. VPS deployment has not started.

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

The first MVP excluded image inputs; Phase 3.6 adds invoice images and scanned-PDF vision fallback without adding local OCR, persistence, Docker, or deployment.

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

## Docker

Docker packages the Python runtime, application code, and exact build-time dependencies into an image. A container is a running instance of that image. This removes laptop-specific Python setup from the deployment boundary: the same tested image can later run on the Ubuntu VPS.

Build the image:

```powershell
docker build --tag extraction-agent:phase4 .
```

Run it with the existing ignored backend environment file:

```powershell
docker run --detach --name extraction-agent --env-file .env --publish 8000:8000 extraction-agent:phase4
```

`--publish 8000:8000` maps host port 8000 to the container's port 8000. Uvicorn listens on `0.0.0.0` inside the container so Docker can forward traffic to it. `--env-file .env` supplies `OPENAI_API_KEY`, model, timeout, and CORS settings at runtime; `.env` is excluded from the build context and never becomes an image layer.

Verify and stop the local container:

```powershell
curl.exe http://127.0.0.1:8000/health
docker stop extraction-agent
docker rm extraction-agent
```

Pillow and PyMuPDF install from Linux wheels on the pinned Debian-based Python image and require no additional operating-system packages for the current JPEG, PNG, and PDF workflows. Re-evaluate this if a future platform lacks compatible wheels or new document features require external binaries.

## Current API

### `GET /health`

Confirms that the API process is available.

### `POST /extractions/invoice`

Accepts one PDF, JPG/JPEG, or PNG multipart upload in the `file` field. The current validation layer:

- Accepts `application/pdf`, `image/jpeg`, and `image/png` with matching file signatures.
- Rejects empty files.
- Rejects files larger than 5 MiB (5,242,880 bytes).
- Limits decoded images to 20 megapixels and normalizes them to at most 2,000 pixels per side.
- Limits scanned-PDF vision fallback to five rendered pages.
- Extracts embedded PDF text with `pypdf` when available.
- Renders image-only PDF pages with PyMuPDF and safely decodes images with Pillow.
- Uses OpenAI vision only for scanned PDFs and image uploads; local OCR is not used.
- Keeps text and vision provider calls behind isolated application interfaces.
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

For an image invoice, change the file path and media type, for example:

```powershell
curl.exe -X POST http://127.0.0.1:8000/extractions/invoice `
  -F "file=@C:\path\to\invoice.jpg;type=image/jpeg"
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

### `POST /extractions/invoice/query`

Accepts JSON containing `question` and an `invoice` that must satisfy the existing `Invoice` schema. Questions are trimmed, must be non-empty, and may contain at most 500 characters. Each request is independent and returns one concise grounded answer.

```json
{
  "question": "What is the total?",
  "invoice": {
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
}
```

The validated invoice is already the complete small context, so this endpoint uses direct grounding rather than RAG, embeddings, or a vector database.

## Invoice Schema

`app/schemas.py` defines the extraction result independently from the provider.

An invoice can contain:

- Vendor, invoice number, invoice date, and three-letter uppercase currency code.
- Subtotal, tax, and total as exact decimal values.
- Line items with a required description and optional quantity, unit price, and amount.
- Warnings describing missing or uncertain source information.

Invoice facts are nullable because real documents can omit them. Missing collections default to empty lists. Unknown fields and invalid values are rejected, and no placeholder values are generated.

## LLM Boundary

`app/llm_extraction.py` contains the provider-specific adapter. The workflow depends on application-owned text and vision interfaces rather than OpenAI SDK calls in the route. Provider timeouts return HTTP 504; provider and invalid structured-output failures return HTTP 502; missing server configuration returns HTTP 503. Error responses do not expose credentials or provider internals.

The current model default is `gpt-5.4-nano`, selected for this bounded, cost-sensitive data-extraction MVP. Model quality must be evaluated against representative invoices before public deployment.

## Error Responses

Errors use FastAPI's `{"detail":"..."}` shape.

| Status | Meaning |
| --- | --- |
| 400 | The uploaded invoice file is empty. |
| 413 | The upload exceeds the 5 MiB limit. |
| 415 | The declared type or file signature is not supported. |
| 422 | The PDF/image is unreadable or exceeds decoded-image/page safety limits. |
| 502 | The provider failed or returned invalid structured output. |
| 503 | The server has no usable provider configuration. |
| 504 | The provider exceeded its configured timeout. |

## Current Limitations

- Only PDF, JPG/JPEG, and PNG invoices are supported, one file per request.
- Scanned PDFs are limited to five pages; images are limited to 20 megapixels and normalized to 2,000 pixels per side.
- Local OCR is not implemented; scanned content depends on the configured vision provider.
- PDF text order can differ from visual layout, especially for complex tables.
- Schema-valid output can still contain extraction mistakes or conservative omissions.
- Ambiguous labels may be returned as null with warnings rather than inferred.
- Files are processed ephemerally; there is no history, persistence, or retry queue.
- The image is built locally but has not been published to a registry or deployed to a VPS.
- The local MVP has no authentication, public-demo rate limiting, Nginx, or production deployment configuration yet.
