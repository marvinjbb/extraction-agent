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

## Provider schemas and domain schemas have different jobs

The dependency-lock release passed offline checks, but its provider smoke test
returned `status=incomplete`, `reason=max_output_tokens`, `output=[]`, and zero
reported usage. That looked like a generation-budget problem, but controlled
isolation showed otherwise:

- the preserved production image and new candidate both reproduced it;
- raw HTTPS reproduced it while plain Responses completed;
- a trivial strict Structured Outputs schema completed;
- the complete Invoice schema failed;
- removing `line_items` did not fix it;
- metadata-only fields completed;
- adding one production `Decimal` field reproduced the failure; and
- changing only that field to `number|null` completed.

The evidence establishes a provider-incompatible or problematic LLM-facing Decimal
JSON Schema representation; it does not establish OpenAI's internal cause. Pydantic
generated `number|string|null`, with a lookahead-based pattern on the string branch,
for every Decimal field.

The fix separates contracts. OpenAI receives `ProviderInvoice`, whose monetary and
quantity fields are strict plain-decimal strings. Application code converts them
with `decimal.Decimal`, rejects malformed/non-finite input without cleanup, and then
validates the result with the authoritative domain `Invoice`. Incomplete responses,
refusals, missing parsed output, conversion failures, and final validation failures
all remain fail-closed. The bounded output budget remains useful, but it was not the
root-cause fix.

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
