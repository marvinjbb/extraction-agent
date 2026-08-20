# Build the application wheel separately so build tooling does not enter runtime.
FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a AS builder

WORKDIR /build

COPY pyproject.toml README.md ./
COPY app ./app

RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels .


FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/* && rm -rf /wheels

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).read()"]

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
