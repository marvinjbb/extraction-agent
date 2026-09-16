# Extraction Agent roadmap

This document preserves implementation history while separating the deployed system
from possible future hardening.

## Current system

**Status:** `DEPLOYED`

The Extraction Agent is an independently deployed FastAPI service connected to the
portfolio at <https://marvinjb.dev/demo/extraction>. It supports:

- One PDF, JPEG, or PNG invoice per request.
- Text-first PDF extraction with pypdf.
- Bounded PyMuPDF/Pillow vision fallback for scans and images.
- OpenAI Structured Outputs plus application-owned Pydantic validation.
- One stateless query grounded in validated invoice JSON.
- A non-root, health-checked Docker runtime with exact dependency constraints.
- Application-generated request IDs and privacy-safe JSON telemetry.
- Offline automated tests and CI for lint, formatting, tests, Docker, and secrets.

## Completed milestones

| Milestone | Status | Result |
| --- | --- | --- |
| Repository and Python 3.12 foundation | Complete | Independent FastAPI project with tests and documentation |
| Upload boundary | Complete | 5 MiB bounded PDF/JPEG/PNG validation and signature checks |
| Invoice contract | Complete | Strict Pydantic invoice/line-item models using Decimal values |
| Embedded PDF parsing | Complete | pypdf text extraction and distinct malformed/text-empty errors |
| Structured extraction | Complete | OpenAI adapter behind application-owned protocols |
| Portfolio integration | Complete | Browser demo with explicit CORS configuration |
| Ask This Invoice | Complete | Stateless question over validated invoice JSON; no RAG |
| Image/scanned PDF support | Complete | Bounded vision route with PyMuPDF and Pillow |
| Containerization and deployment | Complete | Non-root Python 3.12 image behind the public service |
| Professional packaging | Complete | Final docs, CI, dependency lock, secret scan, and observability |

Detailed architectural decisions remain in [DECISIONS.md](DECISIONS.md).

## Future hardening

These are candidates, not commitments or claims about the current service:

1. Build a sanitized/synthetic labeled invoice benchmark with field-level quality,
   latency, and cost metrics.
2. Review public OpenAPI/Swagger exposure.
3. Define proxy and/or application rate/concurrency controls from measured traffic
   and provider cost rather than inventing arbitrary limits.
4. Verify ingress multipart/body-size limits independently from the 5 MiB endpoint
   read boundary.
5. Add arithmetic reconciliation and human review only if product requirements call
   for accounting-grade decisions.
6. Improve mixed-content PDF routing and source-page/coordinate citations if
   representative failures justify the complexity.
7. Add authentication, persistence, durable jobs, or local OCR only when a concrete
   user/data-lifecycle/privacy requirement exists.
