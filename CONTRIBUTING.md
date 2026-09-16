# Contributing

## Development setup

Use Python 3.12 and a virtual environment:

```bash
python -m venv .venv
python -m pip install --constraint requirements.lock -e ".[dev]"
```

Normal development and tests require no OpenAI key. Copy `.env.example` to `.env`
only for explicitly authorized provider work; `.env` must never be committed.

## Required checks

```bash
pytest
ruff check .
ruff format --check .
python -m pip check
docker build --tag extraction-agent:review .
```

## Contribution rules

- Use only synthetic documents and values in fixtures, screenshots, issues, and
  pull requests. Never add real invoices.
- Preserve upload/document safety limits unless a reviewed requirement changes them.
- Keep provider code behind application-owned interfaces and preserve final
  Pydantic validation.
- Keep logs privacy-safe; do not add document text, fields, filenames, questions,
  prompts, provider bodies, or secrets.
- Update `requirements.lock` deliberately when dependency ranges change and verify
  both local installation and Docker build.
- Add focused tests for behavior and failure mappings. Offline CI must never call
  OpenAI or production services.
- Explain contract, privacy, deployment, or limitation changes in the corresponding
  documentation.

Pull requests should be small, describe the user/engineering problem, call out
security/privacy effects, list verification performed, and avoid unrelated cleanup.
