# Lessons learned

## Declared MIME type is not enough

Clients can send an incorrect declaration, so each supported type also needs a
leading-signature check.

## Signature checks are not enough

`%PDF-` does not make a valid PDF. Parser-level handling is still required for
malformed, encrypted, empty, and otherwise unreadable files.

## Separate parsing from AI extraction

Keeping upload validation, PDF parsing, image normalization, model inference, and
schema validation distinct makes failures observable and tests deterministic.

## Provider-specific code belongs behind an application interface

The FastAPI route depends on `InvoiceExtractor`, `VisionInvoiceExtractor`, and
`InvoiceQueryService`, not SDK calls. Tests can replace them and provider changes do
not rewrite transport logic.

## Image support expands the safety surface

Vision support required decoded-pixel limits, frame checks, format verification,
orientation handling, dimension normalization, and a scanned-PDF page limit.

## Text-first routing avoids unnecessary vision cost

Readable PDFs already expose text. Rendering them to images would increase payload,
latency, and provider cost without a demonstrated benefit.

## Scanned PDFs need bounded vision fallback

pypdf extracts embedded text; it is not OCR. Scans therefore need a bounded pixel
path, while local OCR remains unnecessary until requirements justify it.

## Structured Outputs still require local validation

The provider can target a schema, but Pydantic remains the application authority.
Schema validity still does not establish factual correctness.

## Reasoning and visible output share one response budget

The dependency-lock packaging release passed offline checks but its first real
provider smoke test returned an incomplete Responses API result with
`max_output_tokens` as the reason, no output items, and no parsed invoice. Strict
validation failed closed and the deployment automatically rolled back. Both the
known-good and candidate images used the same OpenAI SDK, so this was not a parsed
field-location or dependency-version break. The adapter now provides an explicit
bounded output budget, distinguishes incomplete responses and refusals, and has
regression coverage for the SDK's nested parsed-response structure. It still accepts
only Structured Outputs followed by application-owned `Invoice` validation.

## Validation logs must not leak rejected values

Useful diagnostics need only the validation stage, field path, and error type. Raw
values, documents, prompts, and provider bodies are both unnecessary and risky.

## Date normalization needs regression coverage

Invoices use competing date formats. Explicit examples and regression tests protect
the rule that ambiguous or unreadable dates become null/warnings rather than copied
into an invalid contract.

## RAG was unnecessary for invoice querying

The complete validated invoice fits in direct context. Embeddings and retrieval
would add infrastructure without adding relevant information.
