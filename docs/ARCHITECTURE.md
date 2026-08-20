# Extraction Agent Architecture

## Current State

The `extraction-agent` repository is a separate Git project with a Python 3.12+ development environment and a minimal FastAPI application. `GET /health` returns `{"status":"ok"}`. `POST /extractions/invoice` accepts one PDF upload, applies bounded byte-level validation, extracts embedded text page by page with `pypdf`, and returns a temporary development response. Pydantic models independently define the future structured invoice output. The implemented layers are covered by automated tests.

LLM integration, OCR, databases, Docker, deployment infrastructure, and the public API route have not been implemented. The upload endpoint does not return the invoice schema yet.

## Current Upload Boundary

```text
One multipart file
    ↓
Declared media type is application/pdf
    ↓
Read at most 5 MiB + 1 byte
    ↓
Reject empty or oversized content
    ↓
Verify %PDF- signature
    ↓
Pass validated bytes to PDF extraction
```

The 5 MiB limit is intentionally small for a public portfolio MVP. Checking both the declared media type and the leading PDF signature catches simple mismatches without pretending to fully validate or parse the document. Uploaded content is not persisted.

## Current PDF Text Extraction Boundary

```text
Validated PDF bytes
    ↓
pypdf PdfReader
    ↓
Extract embedded text from each page
    ↓
Trim page text and join readable pages in order
    ↓
Return page count and combined text
```

`pypdf` was selected as the smallest suitable dependency for in-memory, page-by-page text extraction. Malformed or unreadable PDFs produce an application-level extraction error. A readable PDF with no embedded text produces a distinct no-text error explaining that OCR is not supported.

This layer does not infer fields, reconstruct tables, perform OCR, or prove that extracted text matches visual reading order. Complex layouts and unusually large decompressed page content remain known parser limitations to evaluate with representative invoices and before public hardening.

## Current Schema Boundary

```text
Future extraction data
    ↓
Invoice Pydantic model
    ├── nullable document facts
    ├── exact Decimal amounts
    ├── nested LineItem models
    ├── warnings
    └── unknown fields rejected
    ↓
Validated Python data / JSON-ready output
```

The schema is defined before model integration so the future LLM must produce data for an application-owned contract. Pydantic validates types and nested structure, converts supported inputs such as decimal strings, applies defaults, and rejects invalid or unknown fields. It does not decide whether extracted facts are correct.

The intended future flow is:

```text
PDF
 ↓
Upload validation
 ↓
Text extraction
 ↓
LLM extraction
 ↓
Invoice Pydantic schema
 ↓
Validated structured JSON
```

## Approved Local MVP

The first implementation will support one text-based invoice PDF per request.

```text
API client
    |
    | PDF upload
    v
FastAPI endpoint
    |
    v
File validation
    |
    v
PDF text extraction
    |
    v
LLM structured extraction
    |
    v
Schema validation
    |
    v
Structured JSON response
```

The layers should remain distinct:

- **Upload validation:** Determines whether the request and file are supported and safe to process.
- **Document parsing:** Reads embedded text from a text-based PDF.
- **OCR:** Converts pixels into text and is deferred until scanned/image documents are supported.
- **LLM extraction:** Maps document text to the requested invoice fields.
- **Schema:** Defines the required shape and types of the result.
- **Validation:** Proves whether input or generated output satisfies the applicable rules.

The MVP does not require persistent storage: the file can be processed within the request lifecycle and discarded. It also does not require PostgreSQL, Redis, a vector database, RAG, MCP, or a background queue.

## Target Production Integration

```text
Recruiter
    ↓
marvinjb.dev/demo/extraction (React on Hostinger)
    ↓ HTTPS
api.marvinjb.dev/extraction/*
    ↓ DNS / Cloudflare
Ubuntu VPS
    ↓
Nginx
    ↓
Extraction Agent Docker container
    ↓
FastAPI extraction workflow
    ↓
JSON response
    ↓
React result display
```

The React frontend owns file selection, controls, progress, result rendering, and user-facing errors. This repository owns validation, parsing, model calls, schemas, extraction logic, backend errors, and backend telemetry. The integration boundary is a versioned, documented HTTPS API contract.

Before public deployment, the service should have reasonable upload limits, timeouts, CORS policy, secret handling, structured logs, a health endpoint, safe errors, and justified abuse/cost controls. Docker, Nginx, the VPS, and `api.marvinjb.dev` remain target-state components until their roadmap phases are completed.
