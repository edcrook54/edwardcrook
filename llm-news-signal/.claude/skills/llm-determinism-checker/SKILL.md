---
name: llm-determinism-checker
description: Use when reviewing an LLM extraction pipeline for reproducibility - whether re-running it on unchanged input is guaranteed to reproduce the same output, and whether the model/prompt version actually used is logged - triggers on "determinism", "reproducibility", "cached LLM response", "prompt version", "pinned model".
---

# LLM Determinism Checker

## Overview

A statistical claim built on LLM-extracted features is only reproducible if
re-running the extraction on the same input is guaranteed to produce the
same output. This project's `anthropic` SDK version has no `temperature`
parameter at all (removed from the public API), so determinism here rests
entirely on response caching, not a sampling-randomness knob. This skill
checks that the caching mechanism actually delivers that guarantee, and
that every extraction's provenance (model, prompt version) is logged
clearly enough to know exactly what produced a given score.

## When to Use

Before trusting that `make extract` run twice on the same
`fomc_statements.json` would produce the same `extractions.json`, and
before accepting any extraction's score without knowing what model/prompt
version produced it.

## Core Checklist

### 1. Does the cache actually guarantee reproducibility?

- Confirm `_cache_key` hashes `(model, prompt_version, text)` and that
  `ExtractionClient.extract` checks this cache *before* ever calling the
  API - trace the code path, don't just read the docstring's claim.
- Confirm there is no path where a cache hit is skipped or bypassed (e.g. a
  force-refresh flag that silently defaults to on, or a cache file that
  gets cleared by `make extract` itself before reading it).
- Confirm `PROMPT_VERSION` is actually referenced by the tool schema or
  instructions it's meant to version - if the tool schema changes but
  `PROMPT_VERSION` isn't bumped, old cached responses for a changed prompt
  would be silently reused as if they were produced by the new prompt.

### 2. Provenance logging

- Confirm every record in `data/extractions.json` includes `metadata` with
  `model`, `prompt_version`, and `from_cache` - not just the extracted
  score with no record of what produced it.
- Confirm the README/CLAUDE.md accurately describe what determinism
  guarantee exists given the actual installed SDK version - check the
  installed `anthropic` package version's `messages.create` signature
  directly (e.g. via `python -c "import inspect, anthropic; ..."`) rather
  than trusting a comment that might be stale if the SDK was upgraded since
  it was written.

### 3. The "no temperature" claim itself

- Verify this is actually true for the SDK version pinned in
  `pyproject.toml` (`anthropic>=0.40` - check what's actually installed in
  the lockfile/venv, not just the minimum version constraint) rather than
  taking the code comment's word for it. An SDK upgrade could reintroduce
  a `temperature` parameter or a different determinism-relevant control
  (e.g. a seed parameter) that this project should then use and document,
  not silently ignore because an old comment said it didn't exist.

### 4. Live-call safety

- Confirm `ExtractionClient.extract` raises a clear, actionable error
  (naming the missing API key and the config path to set it) rather than
  silently returning a default/empty result when no cached response exists
  and no API key is set - a silent fallback here would be far worse than a
  loud failure, since it could let a downstream analysis run on fabricated
  or missing data without anyone noticing.

## Quick Reference

| Check | Pass condition | Common failure |
|---|---|---|
| Cache-first | Every `extract()` call checks cache before any API call | A bypass path that skips the cache |
| Prompt versioning | `PROMPT_VERSION` bumped whenever the tool schema changes | Stale cached responses reused silently after a prompt change |
| Provenance | `model`, `prompt_version`, `from_cache` logged per extraction | Score stored with no record of what produced it |
| SDK claim verified | "no temperature" checked against the actually-installed SDK | Stale comment trusted without re-verifying |
| Missing-key failure | Loud, actionable `RuntimeError` | Silent fallback to a default/empty result |

## Red Flags

- Any extraction record missing `metadata`.
- A `PROMPT_VERSION` constant that hasn't changed despite a visibly
  different `EXTRACTION_TOOL_SCHEMA` in git history.
- Code reachable without hitting the cache-key check first.

## Rationalization Table

| Excuse | Reality |
|---|---|
| "The cache file will always exist once we've run it once" | True until someone deletes it, changes machines, or the prompt changes without bumping the version - the guarantee needs to hold structurally, not just in the common case. |
| "Temperature doesn't matter, we're using tool-forced structured output anyway" | Structured output constrains the *shape* of the response, not the *values* chosen within that shape - without temperature or a cache, two calls to the same prompt could still return different scores. |

## Output Format

Report findings as Critical / Important / Minor with file:line references,
plus an explicit list of what was checked and verified as sound.
