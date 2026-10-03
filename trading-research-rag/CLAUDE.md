# Project brief for Claude Code

## what this is

Retrieval service (BM25 + LSA hybrid) over the sibling quant projects' docs/notebooks.
SWE-track portfolio piece. Few things working end-to-end > many things half-built.

## rules, don't relitigate

- **Honest > impressive.** Hybrid loses to BM25 here. Say so, show the sweep that
  proves it's not a bad default, don't re-tune till hybrid wins.
- **Gold labels never come from the system's own search output.** Build them with
  `find_chunk.py` (reads corpus directly, never touches bm25/dense/index). Labels from
  eyeballing search results = circular = worthless.
- **CI gates on a real number**: `make eval-gate` vs committed baseline, not vibes.
- `chunk_id` = `f"{repo}/{rel_path}::{idx}[::{heading}]"`. The repo prefix is
  load-bearing: drop it and two projects' `README.md`s collide. Happened once already.
- BM25 uses ATIRE IDF (`ln(1 + (N-n+0.5)/(n+0.5))`), not Robertson-Walker (goes negative
  for common terms). Don't "simplify" back.
- Dense leg is TF-IDF+SVD (LSA), a deliberate choice: transparent, no GPU needed at
  this corpus size. It's a design decision, not a TODO.
- `corpus_roots` point at `edwardcrook/...` (published repo), not outer working copies.

## architecture (implemented, don't redesign)

1. chunk = one md section or one notebook cell (`ingest/chunk.py`)
2. BM25 + RRF from scratch, LSA via sklearn (`retrieval/`)
3. RRF combines by rank, not raw score
4. content-hashed index, `Index.load` raises on hash mismatch
5. two-tier gold eval (hand-labeled + bootstrapped), bootstrap CIs (`eval/`)

## checking it works

1. `make index`: chunk count and hash print sane
2. `make eval`: bm25 > hybrid > dense ordering matches README table
3. `make serve` + manual query: citations real and specific

## non-goals

- no vector-DB framework at this corpus size, brute-force cosine is fine
- don't tune until hybrid wins; the honest "it doesn't" result is more valuable
- no Docker/Grafana yet, `/metrics` is enough for now

## final gate

Once numbers are real: run `project-audit` skill, checkers = `retrieval-validity`,
`production-robustness`, `citation-provenance`, `narrative` (shared).
