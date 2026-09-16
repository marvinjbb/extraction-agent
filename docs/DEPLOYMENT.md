# Deployment

## Production artifact

The Dockerfile uses two digest-pinned Python 3.12 slim stages. The builder resolves
the application through `requirements.lock`; the runtime installs wheels only,
creates a non-root `app` user, exposes internal port 8000, and checks `GET /health`
with the Python standard library.

```bash
docker build --tag extraction-agent:release .
docker run --rm --env-file /secure/runtime/environment \
  --publish 127.0.0.1:8000:8000 extraction-agent:release
```

The example loopback binding assumes a reverse proxy on the same host. Choose the
real host port and network according to the existing VPS topology; do not expose the
container directly merely because Uvicorn listens on `0.0.0.0:8000` internally.

## Runtime configuration

| Variable | Required | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | Yes for extraction/query | Runtime provider secret |
| `OPENAI_MODEL` | No | Defaults to `gpt-5.4-nano` |
| `OPENAI_TIMEOUT_SECONDS` | No | Positive provider deadline; default 30 |
| `FRONTEND_ORIGINS` | No | Comma-separated exact CORS origins |

Keep the environment file outside the release archive, root-readable where
appropriate, and out of image layers, logs, shell history, and Git.

## Conservative release sequence

The repository does not define or claim a particular VPS release script. A safe
manual/container deployment should:

1. Verify the intended commit and local CI-equivalent checks.
2. Build/tag the candidate image without secrets.
3. Preserve the current image tag or digest as the rollback target.
4. Start a candidate with runtime configuration and a loopback/private binding.
5. Wait for container health and call `/health` internally.
6. Smoke-test a **synthetic** text PDF and, when authorized, a synthetic vision case.
7. Switch only the reverse-proxy target/container after checks pass.
8. Confirm public health, CORS, request IDs, and safe JSON logs.
9. Remove old containers only after the rollback window; never remove unrelated
   services.

The verified public topology uses `api.marvinjb.dev` as the reverse-proxy boundary.
No Nginx file is stored here, and this document does not claim a specific proxy body
limit. Ingress/body-size enforcement is important because the endpoint's 5 MiB read
limit occurs after multipart handling begins.

## Health, smoke tests, and rollback

```bash
curl --fail http://127.0.0.1:8000/health
docker inspect --format '{{.State.Health.Status}}' extraction-agent
docker inspect --format '{{.Config.User}}' extraction-agent
docker logs --tail 100 extraction-agent
```

Smoke tests should use synthetic documents and verify expected status, schema, and
`X-Request-ID` without printing provider credentials or document contents. If health
or compatibility fails, stop the candidate and restart the preserved image using
the unchanged runtime environment and binding, then verify health again.

## Troubleshooting

- **503:** confirm the runtime key exists without echoing it.
- **504:** compare provider duration telemetry with application/proxy timeouts.
- **502:** inspect safe provider outcome and validation category, never raw payloads.
- **413:** confirm both proxy and application limits and account for multipart
  overhead.
- **415/422:** check declared type, signature, parser/decoder validity, page/pixel
  limits, and encryption.
- **Browser CORS failure:** verify the exact origin in `FRONTEND_ORIGINS`.

Log inspection should remain metadata-only. Do not enable request-body logging at
the proxy or application for invoice traffic.
