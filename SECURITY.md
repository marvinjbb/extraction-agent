# Security policy

## Scope

This is a public portfolio extraction demo, not an authenticated document-management
system. Do not upload sensitive, regulated, or customer documents without explicit
authorization and compatible organizational/provider policy. Prefer synthetic data.

## Security boundaries

- Runtime secrets stay in ignored/runtime environment files and never in Git.
- Uploads are limited to declared PDF/JPEG/PNG content with matching signatures,
  a 5 MiB application read boundary, parser/decoder checks, a 20-megapixel image
  limit, 2,000-pixel normalization, and a five-page scanned-PDF limit.
- The application does not intentionally persist files, results, or history;
  framework/OS temporary spooling may occur during multipart handling.
- Provider output must pass the application-owned Pydantic schema.
- JSON telemetry uses an allowlist and excludes filenames, contents, extracted
  fields, questions, prompts, raw provider responses, credentials, cookies, and
  sensitive headers.

Text extracted from PDFs, normalized scanned/image content, or validated invoice
JSON plus the query is sent to OpenAI depending on the selected path. No provider
retention claim is made here.

## Current limitations

The public API has no authentication and no application-level rate limiting.
Swagger/OpenAPI remain enabled. Signature checks are not malware scanning, parsers
and vision models have limitations, and schema validity is not factual accuracy.
Proxy body limits, cost controls, concurrency, and public documentation exposure
require deployment-level review.

## Reporting a vulnerability

Use GitHub's repository security reporting mechanism if available, or open a GitHub
issue containing only non-sensitive reproduction details. Never include credentials,
real invoices, private document contents, or exploitable secrets in a public report.
