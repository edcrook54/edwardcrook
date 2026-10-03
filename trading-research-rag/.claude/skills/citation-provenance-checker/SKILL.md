---
name: citation-provenance-checker
description: Use when reviewing a retrieval system's citation/provenance guarantees for correctness - triggers on "citation", "provenance", "chunk id", "source attribution", "traceability", "stale index".
---

# Citation Provenance Checker

## Overview

This project's value proposition over a plain chatbot is that every
returned result cites a real, specific location in the source corpus. That
guarantee has exactly two ways to quietly break: the chunk-id/citation
scheme stops being unique or stops matching what's actually on disk, or the
served index drifts out of sync with the corpus it claims to represent.
This skill checks the provenance chain end to end, from raw file through to
the API response.

## When to Use

Before trusting that a `/search` result's `citation` field actually points
at real, current content — and specifically after any change to
`src/tradingrag/ingest/chunk.py` or the corpus_roots in `config.py`.

## Core Checklist

### 1. chunk_id global uniqueness

- Confirm `chunk_id` is prefixed with `source_repo`, not just the
  file-relative path — check `tests/test_chunk.py` or add a test that
  constructs two same-named files (e.g. `README.md`) under two different
  repo roots and confirms their chunk_ids differ. This exact bug happened
  once already (see `README.md`'s "What running it against real data
  caught"); confirm it cannot recur silently.
- Within a single file, confirm `idx` (the section/cell position) is
  actually sufficient to disambiguate — check whether two sections could
  ever share both the same `idx` and the same `heading` text (unlikely but
  worth a one-line confirmation of why it can't happen given how `idx` is
  assigned).

### 2. Citation accuracy

- Pick several real `/search` responses (or chunks straight from
  `load_corpus`) and manually confirm the `citation()` string's file path
  and section/cell-index actually correspond to real content in the
  `edwardcrook/` repo as it exists right now — not a cached or
  previously-correct mapping.
- For notebook-sourced chunks, confirm `cell_index` matches the *actual*
  cell position in the live `.ipynb` file (open it and count), not an
  off-by-one from skipped-empty-cell handling in `chunk_notebook`.
- For markdown-sourced chunks, confirm the `section` heading text exactly
  matches what's in the file (no truncation, no stray markdown syntax left
  in from the `_HEADER_RE` match).

### 3. Index/corpus staleness

- Confirm there's no path where `make serve` can run against an index
  built from a corpus state that no longer matches what's in
  `edwardcrook/` (e.g. after someone edits a README there without
  re-running `make index`). The content hash detects a mismatch between
  the saved index and its own hash file, but it does **not** detect "the
  source corpus changed since this index was built" — confirm the README
  and CLAUDE.md are honest about this gap rather than implying the hash
  check covers it.
- Check whether `/health`'s reported `index_hash` is actually useful for a
  caller to detect this kind of external drift, or whether that's a gap
  worth naming explicitly as "not yet done."

### 4. Provenance under chunking edge cases

- A notebook markdown cell with multiple headers in one cell: confirm
  `current_heading` tracking in `chunk_notebook` picks a defensible one
  (e.g. the first) and that this is at least a deliberate choice, not an
  accident of iteration order.
- Confirm a code cell immediately following a markdown cell with no header
  at all correctly inherits `(untitled)` rather than some stale heading
  from several cells earlier in a different section.

## Quick Reference

| Check | Pass condition | Common failure |
|---|---|---|
| Global uniqueness | repo-prefixed id, verified with a same-filename-two-repos test | Collision across projects sharing a filename |
| Citation accuracy | Spot-checked citations match real current file content | Stale or off-by-one cell/section reference |
| Corpus drift | README/CLAUDE.md honest about what the hash check does NOT catch | Implied guarantee that doesn't actually exist |
| Chunking edge cases | Heading-inheritance behavior is deliberate, not accidental | Wrong heading carried over from a prior section |

## Red Flags

- Any two chunks in the live index sharing an identical `chunk_id`.
- A citation whose file path or section doesn't exist in the current
  `edwardcrook/` repo content.
- A README claim that the content hash "ensures citations are always
  current" when it only detects index/pickle mismatch, not corpus drift.

## Rationalization Table

| Excuse | Reality |
|---|---|
| "The hash check means citations can't go stale" | The hash only proves the saved index matches its own hash file — it says nothing about whether the underlying corpus files have since changed. These are different guarantees and the README must not conflate them. |
| "Cell index off by one is cosmetic" | A citation that points at the wrong cell is a correctness bug for a system whose entire value proposition is accurate provenance, not a cosmetic issue. |

## Output Format

Report findings as Critical / Important / Minor with file:line references
and, for any citation-accuracy finding, the specific chunk_id and what it
should actually point to. List explicit passes.
