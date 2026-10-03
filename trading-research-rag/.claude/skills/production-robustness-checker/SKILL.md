---
name: production-robustness-checker
description: Use when reviewing a retrieval/search service for production readiness - idempotency, error handling, API edge cases, and whether CI actually exercises the live service - triggers on "idempotent", "production ready", "API error handling", "service robustness", "CI coverage", "edge case".
---

# Production Robustness Checker

## Overview

This project's pitch is specifically that it's "built and CI-gated as a
production retrieval service, not a chatbot demo." That claim is only true
if the engineering backs it up: idempotent reindexing, sane error handling
at the API boundary, and CI that actually runs the service rather than only
unit-testing its internals. This skill checks the production claim against
the actual code, not the README's description of it.

## When to Use

Before accepting "production-ready" or "production-engineering pattern" as
a description of this project, and before treating the CI workflow as
sufficient coverage.

## Core Checklist

### 1. Idempotent reindexing

- Confirm `content_hash()` is computed deterministically regardless of
  input chunk order (check `tests/test_index.py` covers this, not just that
  the implementation sorts; verify the test actually varies order).
- Confirm `Index.load` genuinely refuses to serve a mismatched
  hash/pickle pair instead of warning and continuing. Trace the exact
  exception path from `api.py`'s `/health` and `/search` down to
  `Index.load` to confirm a stale-index failure surfaces as a 503, not a
  silent fallback to whatever's in memory.
- Rebuild the index twice from an unchanged corpus and confirm the hash is
  byte-identical both times (not just "close" or "similar size").

### 2. API error handling and edge cases

- Empty or whitespace-only query string: confirm this is rejected with a
  clear 4xx, not a 500 or a silently empty-but-200 response.
- `top_k` at its boundary values (1, and above the declared max): confirm
  validation actually enforces the declared `ge=1, le=50` rather than those
  being decorative.
- Invalid `mode` value: confirm the regex-constrained `Query` parameter
  actually rejects it before reaching `Index.search`, and that
  `Index.search`'s own `ValueError` branch for an unknown mode is dead code
  only in the sense that the API layer defends it (not that it's actually
  unreachable and untested).
- `/health` and `/search` before an index has ever been built: confirm this
  produces a clear 503 with an actionable message (e.g. pointing at
  `make index`), not an unhandled `FileNotFoundError` traceback leaking to
  the client.

### 3. Ingestion edge cases

- Empty notebook cells, markdown files with no headers at all (everything
  falls into `(preamble)`), and files with headers but empty bodies: confirm
  each is handled without crashing and without producing a zero-length or
  whitespace-only chunk that would pollute the index.
- A markdown file containing a literal `#` inside a code block (not a
  header): check whether the naive line-based header regex could
  misinterpret it, and if so, whether that's disclosed as a known
  limitation rather than silently producing a wrong section label.

### 4. Does CI actually exercise the live service?

- Check `.github/workflows/trading-research-rag.yml` (once it exists) runs
  more than `ruff`/`mypy`/`pytest` against the library code. Confirm there
  is a step that actually builds the index and hits `/health` or `/search`
  over HTTP (e.g. via `uvicorn` + `curl`/`httpx` in CI), not just unit
  tests that import `api.py`'s functions directly in-process. In-process
  TestClient calls are acceptable *if* they genuinely exercise FastAPI's
  routing/validation layer (not calling the underlying functions directly),
  but a real HTTP round-trip is the stronger claim and should be preferred
  if the README asserts "production service."
- Confirm the CI path filter actually matches this project's directory
  (compare against `pm-bayes-pricer`'s workflow's filter pattern). A
  misconfigured path filter would mean this project's changes never
  actually trigger its own CI.

### 5. Observability honesty

- The README's "Not yet done" section states the Docker/Grafana stack
  isn't wired up and that only `/metrics` (Prometheus text format) is
  exposed directly. Confirm this is actually true by hitting `/metrics`
  and confirming it returns real counters/histograms, not a stub. An
  unwired observability claim in either direction (claiming more or less
  than what's there) is a narrative-honesty issue as much as a robustness
  one.

## Quick Reference

| Check | Pass condition | Common failure |
|---|---|---|
| Idempotency | Same corpus -> byte-identical hash, twice | Hash varies with chunk ordering |
| Stale index handling | `/health`/`/search` return 503 with a clear message | Unhandled traceback or silent stale serve |
| API validation | Boundary/invalid inputs rejected at the API layer | Validation only exists in docstrings |
| CI service coverage | A real build-index-then-query step in CI | CI only imports internal functions |
| Observability honesty | `/metrics` genuinely returns live data | Endpoint exists but is empty/stubbed |

## Red Flags

- A `try/except` around index loading that swallows the error and returns
  an empty result instead of a 503.
- CI that passes `pytest` but never actually starts the service.
- A "not yet done" claim in the README that turns out to already be done
  (or vice versa). Either direction undermines the project's own honesty
  standard.

## Rationalization Table

| Excuse | Reality |
|---|---|
| "The tests import api.py's functions, that's basically testing the API" | Importing and calling a FastAPI route function directly skips request parsing, validation, and the ASGI layer entirely. It tests the handler logic, not the API contract. |
| "An empty query is a user error, not something to handle" | A production service returns a clear 4xx for bad input; letting it fall through to an unhandled exception is exactly the gap between "demo" and "production" this project claims to close. |

## Output Format

Report findings as Critical / Important / Minor with file:line references
and a concrete suggested fix or test to add. List explicit passes.
