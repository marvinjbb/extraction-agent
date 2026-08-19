# DOCUMENT EXTRACTION AGENT — REPOSITORY INSTRUCTIONS

## Scope

This repository contains the backend and agent logic for the Document Extraction Agent in the AI Agent Portfolio Platform. It inherits the relevant principles and accepted architecture from the master `marvinjb.dev` repository, but these instructions govern work inside `extraction-agent`.

The project is built collaboratively as a learning-focused, production-minded portfolio project. Explain meaningful design decisions before implementing them, build incrementally, verify each step, expose failure modes, and make sure the system remains understandable in an AI engineering interview.

## Repository Boundary

This repository owns:

- The Python/FastAPI extraction API.
- Upload and request validation.
- Document parsing.
- OCR only when a supported document genuinely requires it.
- LLM-based structured extraction.
- Schemas and output validation.
- Extraction workflow and backend error handling.
- Backend tests, configuration, documentation, and deployment artifacts.
- Later production concerns such as Docker, health checks, structured logging, security, and observability.

This repository does not own:

- The `marvinjb.dev` portfolio website.
- The React demo interface at `marvinjb.dev/demo/extraction`.
- Research Agent or Voice Agent logic.
- Shared VPS provisioning or global Nginx configuration, except for service-specific documentation or configuration explicitly placed here later.

The portfolio and this service will communicate through a documented HTTPS API. They must not import code from one another or share client-side secrets.

## Approved MVP

The first useful MVP accepts one text-based invoice PDF and returns validated structured JSON.

Initial flow:

```text
PDF upload
    ↓
File validation
    ↓
Text extraction
    ↓
LLM extraction
    ↓
Schema validation
    ↓
JSON response
```

Initial output should cover vendor, invoice number, invoice date, currency, subtotal, tax, total, line items, and useful warnings or nullable fields. Do not invent an uncalibrated numeric confidence score.

The first MVP excludes image uploads, OCR, multiple document types, authentication, databases, persistent file storage, queues, Docker, VPS deployment, Nginx, and broad observability. These are later phases, not forgotten requirements.

## Engineering Principles

- Start with the smallest working local system.
- Do not generate large unexplained portions of the application.
- Explain what we are building, why, where it fits, inputs, outputs, connections, verification, likely failures, and interview-level understanding.
- Distinguish common production practice (`STANDARD`) from project-specific choices (`CUSTOM`).
- Prefer simple, explicit architecture over impressive-looking infrastructure.
- Do not add PostgreSQL, Redis, a vector database, object storage, queues, RAG, MCP, or other services without a concrete requirement.
- Keep parsing, OCR, LLM extraction, schemas, and validation conceptually distinct.
- Keep provider-specific code behind a clear boundary when an LLM provider is selected.
- Use environment variables for secrets. Never commit API keys, credentials, tokens, uploaded private documents, or production data.
- Add dependencies only when their purpose is understood and documented.
- Keep important code testable and important failures visible.
- Update repository documentation and decision records as the architecture evolves.

## Build Order

Work sequentially unless the user explicitly approves a change:

1. Agree on the MVP architecture and folder structure.
2. Establish the Python project and local development workflow.
3. Define API and extraction schemas.
4. Add safe PDF upload and validation.
5. Extract text from supported PDFs.
6. Add LLM structured extraction.
7. Validate outputs and handle failures.
8. Add focused automated tests and local documentation.
9. Integrate locally with the portfolio React demo.
10. Containerize only after the local workflow works.
11. Deploy and route through `api.marvinjb.dev/extraction/*` only in the approved deployment phases.
12. Add proportionate production logging, health checks, security, limits, and observability before public release.

Do not skip ahead without explicit approval.

## Code and Change Rules

- Before creating an important file, explain why it exists and where it belongs.
- Comment architectural intent, not obvious syntax.
- Verify changes with the smallest relevant command or test.
- Do not hide failures behind generated configuration.
- Preserve user changes and avoid unrelated edits.
- Keep commits focused and never commit secrets or untracked local artifacts.
- GitHub is the source of truth for deployable code; production deployment must not depend on untracked local state.

## Documentation

- `README.md` explains the project to developers and recruiters.
- `docs/ARCHITECTURE.md` describes current and target service architecture.
- `docs/ROADMAP.md` is the living implementation tracker.
- `docs/DECISIONS.md` is the append-only ADR log. When a decision changes, mark the old ADR `SUPERSEDED` and reference its replacement.

Keep documentation accurate. Never describe target components as already implemented.

