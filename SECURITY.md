# Security Policy

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security reports.

Email the maintainers privately with:

- a description of the issue and its impact,
- the affected file or endpoint,
- a minimal reproduction,
- any suggested mitigation.

We will acknowledge within a few business days and coordinate a fix and disclosure timeline.

## Hardening summary

The repository ships with several production-hardening properties documented in `PRODUCTION_HARDENING_REPORT.md`:

- **Checkpoint loading uses `torch.load(weights_only=True)`** with file-existence and `.pt` suffix checks. Regression tests in `tests/server/test_server.py::TestCheckpointSafety` lock this in.
- **FastAPI server is concurrent-safe** via per-request agent isolation; the shared resource is the read-only `NetworkWrapper`.
- **All HTTP errors return structured JSON** with a `request_id`; Python tracebacks never reach the client.
- **CORS** is disabled by default; enable via `POKEMON_AI_CORS_ORIGINS`.
- **Request timeouts** enforced via `POKEMON_AI_REQUEST_TIMEOUT_S` (default 30s) → 504 with the structured envelope.
- **Docker image runs as non-root** (uid 1000) with a curated `.dockerignore`.

## What is *not* protected by code

- **Authentication.** Every endpoint is intentionally unauthenticated by default. If you expose this server to the public internet, put it behind an authenticating reverse proxy (Cloudflare Access, Cognito, etc.) — this is documented in `SECURITY` and in `kaggle_writeup.md`.
- **Rate limiting.** Same as above — proxy concern.
