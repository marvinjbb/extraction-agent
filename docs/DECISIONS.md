# Extraction Agent Architecture Decision Record Log

This is a living ADR log. Append future architectural decisions rather than silently replacing earlier decisions. If a decision changes, mark the earlier ADR `SUPERSEDED` and reference its replacement.

## ADR-001 — Maintain the Extraction Agent in a separate repository

**Decision ID:** ADR-001  
**Status:** ACCEPTED  
**Classification:** CUSTOM

**Context:** The portfolio UI and each agent are intended to be independently understandable and deployable projects.

**Decision:** Keep backend extraction logic in `extraction-agent`; keep the React demo and portfolio presentation in `marvinjb.dev`.

**Why:** This creates a focused history, dependency boundary, README, test workflow, and deployment unit for the project.

**Tradeoffs:** Cross-repository API changes require coordination, and some shared conventions may be duplicated.

**When we should reconsider it:** If substantial shared code or atomic cross-project releases make the repository split demonstrably harder to maintain than a monorepo.

---

## ADR-002 — Start with text-based invoice PDFs only

**Decision ID:** ADR-002  
**Status:** ACCEPTED  
**Classification:** CUSTOM

**Context:** Supporting scans, images, OCR, and many document types would combine multiple uncertain problems before the basic workflow is proven.

**Decision:** The first MVP accepts one text-based invoice PDF per request. Image uploads, OCR, and other document types are deferred.

**Why:** It isolates parsing and structured extraction, shortens feedback loops, and creates a useful demonstrable workflow.

**Tradeoffs:** Scanned invoices and images are rejected initially, so the MVP covers only part of the eventual user experience.

**When we should reconsider it:** After the text-based PDF workflow is reliable and representative scanned-document requirements and evaluation samples are defined.

---

## ADR-003 — Prefer Python and FastAPI for the backend

**Decision ID:** ADR-003  
**Status:** ACCEPTED  
**Classification:** CUSTOM

**Context:** The service needs typed HTTP APIs, validation, async support, generated API documentation, and access to Python AI/document tooling.

**Decision:** Use Python with FastAPI unless a concrete project constraint makes another backend materially better.

**Why:** It aligns with the platform architecture and supports a clear, testable API with a small conceptual surface.

**Tradeoffs:** Python dependency and async behavior require deliberate management; FastAPI does not itself solve extraction quality, deployment, persistence, or security.

**When we should reconsider it:** If measured performance, protocol, dependency, provider, or operating constraints demonstrate a better runtime choice.

---

## ADR-004 — Process MVP uploads ephemerally

**Decision ID:** ADR-004  
**Status:** ACCEPTED  
**Classification:** STANDARD

**Context:** The MVP does not require user accounts, document history, asynchronous jobs, or later retrieval of uploaded files.

**Decision:** Process each uploaded PDF within the request lifecycle and do not persist it after processing.

**Why:** Avoiding unnecessary storage reduces privacy exposure, data lifecycle obligations, infrastructure, and failure modes.

**Tradeoffs:** Requests cannot resume after failure, users cannot retrieve history, and long-running work remains bounded by request timeouts.

**When we should reconsider it:** When a defined requirement needs job resumption, audit history, user retrieval, asynchronous processing, or durable artifacts.

---

## ADR-005 — Do not add databases or retrieval infrastructure to the MVP

**Decision ID:** ADR-005  
**Status:** ACCEPTED  
**Classification:** STANDARD

**Context:** The initial workflow transforms one uploaded document into one immediate response and has no demonstrated persistence, caching, queueing, or semantic retrieval requirement.

**Decision:** Do not add PostgreSQL, Redis, a vector database, object storage, RAG, MCP, or a background queue to the first MVP.

**Why:** Requirement-driven infrastructure keeps the service understandable and avoids cost and operational complexity without user value.

**Tradeoffs:** A later requirement may require adding a service and migrating the workflow rather than relying on a prebuilt general-purpose stack.

**When we should reconsider it:** When a concrete data lifecycle, caching, queue, session, rate-limit, file persistence, or semantic retrieval requirement appears.

---

## ADR-006 — Return validated structured data without an invented confidence score

**Decision ID:** ADR-006  
**Status:** ACCEPTED  
**Classification:** STANDARD

**Context:** An LLM-generated numeric confidence value can appear authoritative without being calibrated against measured extraction accuracy.

**Decision:** Return typed invoice fields with nullable values and useful warnings where appropriate. Do not expose a numeric confidence score until a defensible evaluation and calibration method exists.

**Why:** Schema validation can confirm shape and types, while warnings can communicate uncertainty without presenting unsupported precision.

**Tradeoffs:** Consumers receive less convenient ranking information and must handle missing or warned fields explicitly.

**When we should reconsider it:** After a labeled evaluation dataset and a tested calibration method demonstrate that confidence values predict extraction correctness usefully.

---

## ADR-007 — Limit MVP uploads to 5 MiB and verify the PDF signature

**Decision ID:** ADR-007  
**Status:** ACCEPTED  
**Classification:** CUSTOM

**Context:** The public portfolio MVP needs a clear upload boundary before document parsing exists. A declared media type alone can be incorrect or trivially spoofed, while unbounded reads create unnecessary memory and cost risk.

**Decision:** Accept one `application/pdf` upload no larger than 5 MiB, read at most the limit plus one byte, reject empty content, and require the content to begin with the `%PDF-` signature.

**Why:** Five MiB is sufficient for representative text-based invoice PDFs while keeping local and future public requests bounded. The signature check catches basic media-type mismatches without claiming to fully parse or prove the document is safe.

**Tradeoffs:** Some legitimate large PDFs are rejected, and a matching signature does not guarantee a well-formed or safe PDF. Full structural validation remains the parser's responsibility in a later phase.

**When we should reconsider it:** Reconsider the size when representative documents or measured usage justify a different limit. Reconsider validation depth when parsing, malware scanning, storage, or public threat requirements are introduced.

---

## ADR-008 — Use Decimal values and nullable source facts in invoice schemas

**Decision ID:** ADR-008  
**Status:** ACCEPTED  
**Classification:** STANDARD

**Context:** Invoice extraction must represent financial values accurately while acknowledging that real documents frequently omit fields. Binary floating-point values can introduce rounding artifacts, and invented placeholders would misrepresent missing source information.

**Decision:** Represent quantities and monetary values with Python `Decimal`. Make invoice-level source facts nullable, default line items and warnings to independent empty lists, require a non-empty description for every line item, and reject unknown fields.

**Why:** Decimal arithmetic preserves base-10 values used in financial documents. Nullable fields preserve the difference between absent information and fabricated defaults. Required line-item descriptions keep nested objects meaningful, while strict unknown-field handling exposes misspelled or unsupported model output.

**Tradeoffs:** Decimal values require deliberate JSON serialization and can accept valid decimal strings through Pydantic conversion. A fully nullable invoice model can validate even when few facts were extracted, so extraction-quality checks and warnings remain separate responsibilities.

**When we should reconsider it:** Reconsider field requirements after evaluating representative invoices and downstream UI needs. Reconsider decimal precision or currency modeling if arithmetic, multi-currency conversion, or accounting-grade requirements are introduced.

---

## ADR-009 — Use pypdf for MVP embedded-text extraction

**Decision ID:** ADR-009  
**Status:** ACCEPTED  
**Classification:** CUSTOM

**Context:** Phase 1D needs only in-memory, page-by-page extraction of embedded text from validated PDFs. Rich table analysis, coordinate-level inspection, OCR, PDF modification, and broad document-format support are outside the current scope.

**Decision:** Use `pypdf` to read validated PDF bytes and extract embedded text from each page. Combine non-empty page text in page order, report the original page count, and return distinct application errors for unreadable PDFs and PDFs with no extractable text.

**Why:** `pypdf` directly supports the required page iteration and text extraction with a small pure-Python dependency surface. `pdfplumber` adds layout, object, and table tooling that is not yet required. PyMuPDF offers broader and faster native-backed capabilities but adds unnecessary scope and licensing considerations for this MVP.

**Tradeoffs:** PDF text order and layout can be ambiguous, table structure is not preserved, and image-only PDFs produce no text. Parsing may expand compressed page content beyond the uploaded file size, so representative-document testing and production resource controls remain necessary.

**When we should reconsider it:** Reconsider after evaluating real invoices if text order, tables, layout coordinates, performance, memory behavior, or supported PDF variants make a richer parser demonstrably necessary. OCR requires a separate explicit decision.
