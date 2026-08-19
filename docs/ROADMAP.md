# Extraction Agent Roadmap

This is the living progress tracker for the Extraction Agent. Update statuses and completion evidence as meaningful milestones are completed. Allowed statuses are `NOT STARTED`, `IN PROGRESS`, `COMPLETE`, and `BLOCKED`.

## Current Focus

**Phase 1B — Invoice PDF upload and validation**

**Status:** `COMPLETE`

The API accepts one PDF, enforces media-type, signature, empty-file, and 5 MiB size validation, and returns temporary acceptance metadata. Ruff, automated tests, and live multipart requests have verified the boundary. The next phase must not begin until review.

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

**Status:** `NOT STARTED`

**Goal:** Define the structured invoice response without adding parsing or model calls.

**Major deliverables:** Response/error models, invoice and line-item schemas, examples, and schema tests.

**Understanding required:** API contracts, structured outputs, schemas versus validation, required versus nullable fields, and why uncalibrated confidence is excluded.

**Completion criteria:** Representative valid and invalid structured payloads behave as documented and the contract is ready for workflow implementation.

## Phase 1D — PDF text extraction

**Status:** `NOT STARTED`

**Goal:** Extract usable embedded text from accepted text-based PDFs.

**Major deliverables:** PDF parser decision, parser boundary, empty/scanned-document detection, safe errors, and parser tests.

**Understanding required:** Document parsing versus OCR, PDF structure, in-memory file lifecycle, malformed-document failures, and parser limitations.

**Completion criteria:** Supported PDFs yield text; malformed, text-empty, and scanned PDFs fail clearly; behavior is tested.

## Phase 1E — LLM structured invoice extraction

**Status:** `NOT STARTED`

**Goal:** Convert extracted invoice text into schema-valid structured data.

**Major deliverables:** Provider decision, provider boundary, prompt/extraction workflow, environment-based credentials, output validation, and representative tests/evaluations.

**Understanding required:** Model/provider tradeoffs, prompts, structured generation, deterministic validation, hallucination risks, retries, timeouts, and cost boundaries.

**Completion criteria:** Representative text-based invoices produce schema-valid results; failures do not expose secrets or fabricate success; quality limitations are documented.

## Phase 1F — Complete and verify the local MVP

**Status:** `NOT STARTED`

**Goal:** Prove the complete local request-to-response workflow.

**Major deliverables:** End-to-end API path, consistent errors, focused test suite, sample/synthetic fixtures, run instructions, and updated README.

**Understanding required:** How a request moves through every backend layer, where failures occur, how tests isolate those layers, and what remains outside the MVP.

**Completion criteria:** The service starts locally, processes representative text-based invoice PDFs into validated JSON, rejects expected invalid inputs, and passes its documented tests.

## Later platform phases

**Status:** `NOT STARTED`

After local MVP approval, work proceeds through portfolio UI integration, Dockerization, VPS deployment, Nginx/API routing, public integration, and proportionate production hardening in alignment with the master `marvinjb.dev` roadmap. These phases must not be pulled forward without approval.
