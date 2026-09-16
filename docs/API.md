# API

Base service: `https://api.marvinjb.dev`

All responses include an application-generated `X-Request-ID`. Caller-supplied IDs
are ignored. Errors use FastAPI's normal `{"detail":"..."}` shape; no custom
envelope is invented.

## `GET /health`

Process liveness check.

```json
{"status":"ok"}
```

## `POST /extractions/invoice`

Send `multipart/form-data` with one field named `file`.

Accepted declarations:

- `application/pdf`
- `image/jpeg` (including `.jpg`/`.jpeg` clients)
- `image/png`

The application reads at most 5 MiB plus one byte, checks the declaration and leading
signature, then applies parser/image limits. This endpoint boundary is not a
substitute for an ingress multipart body limit.

```bash
curl -X POST https://api.marvinjb.dev/extractions/invoice \
  -F "file=@synthetic-invoice.pdf;type=application/pdf"
```

Representative sanitized response:

```json
{
  "vendor": "Acme Supplies",
  "invoice_number": "INV-1001",
  "invoice_date": "2026-08-20",
  "currency": "USD",
  "subtotal": "100.00",
  "tax": "8.25",
  "total": "108.25",
  "line_items": [
    {
      "description": "Synthetic consulting service",
      "quantity": "1",
      "unit_price": "100.00",
      "amount": "100.00"
    }
  ],
  "warnings": []
}
```

Invoice-level fields are nullable. `line_items` and `warnings` are arrays. Monetary
values serialize as exact decimal strings. Unknown fields are rejected.

## `POST /extractions/invoice/query`

Accepts JSON containing one trimmed, non-empty question of at most 500 characters
and one schema-valid invoice.

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

```json
{"answer":"The invoice total is USD 108.25."}
```

Each question is independent. The provider receives the validated invoice JSON and
question, not the original file or prior conversation.

## Errors

| Status | Source | Meaning |
| --- | --- | --- |
| 400 | upload | Empty file |
| 413 | upload | More than 5 MiB read by the application |
| 415 | upload | Unsupported declaration or signature mismatch |
| 422 | document/request | Unreadable/unsupported document safety condition, or FastAPI/Pydantic request validation |
| 502 | provider | Provider failure, missing answer, or invalid structured output |
| 503 | configuration | Provider configuration unavailable |
| 504 | provider | Configured provider timeout exceeded |

`OPENAI_TIMEOUT_SECONDS` defaults to 30 seconds. Reverse-proxy and client timeouts
must allow the expected provider latency; changing them does not change the
application's provider deadline.

## CORS and generated documentation

`FRONTEND_ORIGINS` is a comma-separated exact allowlist. The application allows GET
and POST with `Accept`/`Content-Type`, does not enable browser credentials, and
exposes `X-Request-ID`. FastAPI's `/docs`, `/redoc`, and `/openapi.json` remain
enabled; production exposure is a separate hardening decision.
