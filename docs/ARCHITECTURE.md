# Extraction Agent Architecture

## Current State

The `extraction-agent` repository is a separate Git project with a Python 3.12+ FastAPI application. `GET /health` returns `{"status":"ok"}`. `POST /extractions/invoice` accepts one PDF upload, applies bounded byte-level validation, extracts embedded text page by page with `pypdf`, requests schema-constrained invoice facts through an isolated OpenAI adapter, validates them with Pydantic, and returns structured JSON. The implemented layers are covered by automated tests and one controlled live provider check.

OCR, databases, Docker, deployment infrastructure, and the public API route have not been implemented.

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

## Current LLM and Schema Boundary

```text
Extracted document text
    ↓
InvoiceExtractor application interface
    ↓
OpenAI Responses API + Structured Outputs
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

The provider adapter is kept outside the route and returns the application-owned `Invoice` contract. OpenAI Structured Outputs constrains generation to that shape, while Pydantic remains the final local validation boundary. It validates types and nested structure, converts supported inputs such as decimal strings, applies defaults, and rejects invalid or unknown fields. Neither schema compliance nor type validation proves that extracted facts are correct.

Credentials, the model name, and the provider timeout come from environment variables. The default model is `gpt-5.4-nano`, selected for low-cost extraction. Tests inject fakes at the `InvoiceExtractor` boundary and never require a key or make paid requests. Provider timeouts, API failures, missing configuration, and invalid structured results map to explicit application errors.

The implemented local flow is:

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
