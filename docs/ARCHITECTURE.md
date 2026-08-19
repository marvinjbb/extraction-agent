# Extraction Agent Architecture

## Current State

The `extraction-agent` repository has been established as a separate local Git project. It currently contains documentation only. FastAPI, PDF parsing, schemas, LLM integration, Docker, deployment infrastructure, and the public API route have not been implemented.

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

