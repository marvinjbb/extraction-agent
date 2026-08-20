# Extraction Agent Roadmap

This is the living progress tracker for the Extraction Agent. Update statuses and completion evidence as meaningful milestones are completed. Allowed statuses are `NOT STARTED`, `IN PROGRESS`, `COMPLETE`, and `BLOCKED`.

## Current Focus

**Platform Phase 4 — Dockerize Extraction Agent**

**Status:** `COMPLETE`

The unchanged backend is packaged in a locally built and verified non-root container. Health, text extraction, vision extraction, and Ask This Invoice pass through the container. VPS deployment remains a later phase.

## Foundation — Repository and project documentation

**Status:** `COMPLETE`

**Goal:** Establish an independent repository with clear scope, architecture, decisions, roadmap, and recruiter-facing context.

**Major deliverables:** Git repository, GitHub origin, `AGENTS.md`, `README.md`, architecture, roadmap, and ADR log.

**Understanding required:** Repository boundaries, the approved MVP, the frontend/backend contract, and the difference between current and target architecture.

**Completion criteria:** The foundation is reviewed and approved, the empty GitHub repository is connected, and the initial documentation is committed and pushed with explicit approval.

## Phase 1A — Python project and local development foundation

**Status:** `COMPLETE`

**Goal:** Establish the smallest understandable Python/FastAPI development environment without extraction logic.

**Major deliverables:** Approved folder structure, dependency configuration, environment example, ignore rules, minimal application entry point, and test runner.

**Understanding required:** Python environments, dependencies, application entry points, configuration, and test discovery.

**Completion criteria:** A new developer can install dependencies, run the minimal service and tests locally, and no secret is committed.

## Phase 1B — Invoice PDF upload and validation

**Status:** `COMPLETE`

**Goal:** Safely accept one invoice PDF without parsing or extracting its contents.

**Major deliverables:** Multipart upload endpoint, 5 MiB size limit, media-type and PDF-signature checks, empty-file rejection, temporary acceptance response, and validation tests.

**Understanding required:** Multipart uploads, MIME declarations versus content signatures, bounded reads, HTTP error status codes, and upload validation versus document parsing.

**Completion criteria:** A valid PDF is accepted; non-PDF, empty, oversized, and signature-mismatched files fail clearly; Ruff, tests, and a live request pass.

## Phase 1C — API contract and invoice schemas

**Status:** `COMPLETE`

**Goal:** Define the structured invoice response without adding parsing or model calls.

**Major deliverables:** Response/error models, invoice and line-item schemas, examples, and schema tests.

**Understanding required:** API contracts, structured outputs, schemas versus validation, required versus nullable fields, and why uncalibrated confidence is excluded.

**Completion criteria:** Representative valid and invalid structured payloads behave as documented and the contract is ready for workflow implementation.

## Phase 1D — PDF text extraction

**Status:** `COMPLETE`

**Goal:** Extract usable embedded text from accepted text-based PDFs.

**Major deliverables:** PDF parser decision, parser boundary, empty/scanned-document detection, safe errors, and parser tests.

**Understanding required:** Document parsing versus OCR, PDF structure, in-memory file lifecycle, malformed-document failures, and parser limitations.

**Completion criteria:** Supported PDFs yield text; malformed, text-empty, and scanned PDFs fail clearly; behavior is tested.

## Phase 1E — LLM structured invoice extraction

**Status:** `COMPLETE`

**Goal:** Convert extracted invoice text into schema-valid structured data.

**Major deliverables:** Provider decision, provider boundary, prompt/extraction workflow, environment-based credentials, output validation, and representative tests/evaluations.

**Understanding required:** Model/provider tradeoffs, prompts, structured generation, deterministic validation, hallucination risks, retries, timeouts, and cost boundaries.

**Completion criteria:** Representative text-based invoices produce schema-valid results; failures do not expose secrets or fabricate success; quality limitations are documented.

**Completion evidence:** Ruff, 29 automated tests, and dependency integrity checks pass. Mocked tests cover the provider boundary and full endpoint flow without a key. One controlled live request returned a schema-valid invoice through the complete Phase 1E pipeline.

## Phase 1F — Complete and verify the local MVP

**Status:** `COMPLETE`

**Goal:** Prove the complete local request-to-response workflow.

**Major deliverables:** End-to-end API path, consistent errors, focused test suite, sample/synthetic fixtures, run instructions, and updated README.

**Understanding required:** How a request moves through every backend layer, where failures occur, how tests isolate those layers, and what remains outside the MVP.

**Completion criteria:** The service starts locally, processes representative text-based invoice PDFs into validated JSON, rejects expected invalid inputs, and passes its documented tests.

**Completion evidence:** Ruff, 35 deterministic automated tests, and dependency integrity checks pass. The suite covers three representative PDF workflows and all defined validation, parsing, configuration, provider, timeout, and structured-output failures. Two controlled real end-to-end requests returned HTTP 200 and schema-valid JSON. Known parser and model-quality limitations are documented.

## Phase 1 — Local Extraction Agent MVP

**Status:** `COMPLETE`

Phases 1A through 1F are complete. The repository now provides the approved backend-only local MVP: one text-based invoice PDF enters an ephemeral validated pipeline and returns an application-validated structured invoice response. No later platform infrastructure has been pulled forward.

## Platform Phase 3 — Local portfolio integration

**Status:** `COMPLETE`

The `marvinjb.dev` demo submits one multipart `file` to this service through an environment-configured local URL. Explicit local origins are allowed with CORS, and automated plus controlled browser checks verify response and failure handling without moving parsing, provider credentials, or business logic into the frontend.

## Platform Phase 3.5 — Ask This Invoice

**Status:** `COMPLETE`

The backend accepts a validated `Invoice` plus one bounded question, constructs the grounded provider request internally, and returns one answer. Questions are independent, automated tests use fakes, and no PDF, retrieval system, conversation database, or frontend provider configuration is introduced.

## Platform Phase 3.6 — Image and scanned invoice support

**Status:** `COMPLETE`

Text PDFs retain the `pypdf` path. PDFs without embedded text fall back to bounded page rendering and vision extraction; JPG/JPEG and PNG uploads enter the same vision boundary after safe decoding and normalization. Every route ends at the existing `Invoice` Pydantic schema, and Ask This Invoice remains unchanged. Tests use fakes; one controlled provider verification covers the new vision path.

## Platform Phase 4 — Dockerize Extraction Agent

**Status:** `COMPLETE`

The multi-stage Dockerfile builds runtime wheels separately, installs only application dependencies into a pinned Python 3.12 slim runtime, and runs Uvicorn as an unprivileged user on `0.0.0.0:8000`. `.dockerignore` excludes secrets and development artifacts. The 125.7 MB image is healthy and locally verified for text PDF extraction, image vision extraction, and invoice querying. No VPS, proxy, registry, or CI/CD configuration is included.

## Later platform phases

**Status:** `NOT STARTED`

After Dockerization, work proceeds through VPS deployment, Nginx/API routing, public integration, and proportionate production hardening in alignment with the master `marvinjb.dev` roadmap. These phases must not be pulled forward without approval.
