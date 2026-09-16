# Evaluation

## Offline / deterministic testing

The automated suite substitutes provider boundaries with fakes and makes no OpenAI
calls. It validates behavior that application code can determine reliably.

### Upload safety

- Empty and oversized files.
- Unsupported declarations and signature mismatches.
- Malformed, encrypted, text-empty, and zero-page PDFs.
- Invalid, multi-frame, and over-pixel-limit images.
- Image normalization to the 2,000-pixel dimension bound.
- Scanned-PDF five-page bound.

### Routing

- PDFs with embedded text use the pypdf/text path.
- PDFs without embedded text use bounded vision rendering.
- JPEG and PNG uploads use the vision path.

### Schema

- Nullable source fields and independent default collections.
- Finite decimal conversion and JSON serialization.
- Date parsing/normalization regressions and currency format.
- Required line-item descriptions and rejection of unknown fields.

### Provider failures

- Missing configuration.
- Timeout and provider transport failure.
- Missing or malformed structured output.
- Safe validation diagnostics that omit rejected values and document content.

### API and operations

- Health, extraction, and query response contracts.
- CORS allowlist behavior and exposed `X-Request-ID`.
- Application-generated request IDs rather than caller-trusted IDs.
- 400/413/415/422/502/503/504 mappings.
- JSON telemetry allowlisting.

Run locally:

```bash
python -m pip install --constraint requirements.lock -e ".[dev]"
pytest
ruff check .
ruff format --check .
```

## Provider quality evaluation

Provider quality is a different question from deterministic correctness. The
repository currently has **no scored extraction-accuracy benchmark** and therefore
makes no claim about precision, recall, exact-match rate, field accuracy,
hallucination rate, or layout-specific success.

A defensible future evaluation needs a versioned, sanitized or synthetic dataset
containing representative text PDFs, scans, images, sparse invoices, multiple date
formats, complex tables, and ambiguous fields. Human labels should define expected
values and acceptable warnings. Useful metrics include per-field exact/normalized
match, nullable-field handling, line-item set/order accuracy, schema failure rate,
latency, and cost. Arithmetic reconciliation should be measured separately rather
than inferred from schema validity.

No real invoices should enter the repository as fixtures. Provider evaluation must
be an explicit, cost-aware process with authorized synthetic inputs and must not run
in ordinary CI.
