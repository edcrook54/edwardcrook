# Project brief for Claude Code

## What this is

A portfolio project demonstrating production retrieval-system engineering —
software-engineering track evidence for AI Engineer roles (e.g. Oliver Wyman's
Quotient AI / WAVE team), sitting alongside `crypto-cointegration-signal` and
`pm-bayes-pricer`. It lives on a public GitHub repo. Prioritise a small number
of things that actually work end-to-end, with a rigorously evaluated result,
over a large number of half-built things.

## Non-negotiable values

- **Honesty over impressiveness.** If hybrid retrieval doesn't beat BM25 alone
  on this corpus, say so and show the parameter sweep that ruled out "bad
  default" as the explanation — don't quietly re-tune until hybrid wins, and
  don't bury the finding.
- **Gold labels never come from the system's own output.** Every
  `analyst_gold.json` entry must be findable independently via
  `python -m tradingrag.eval.find_chunk`, which reads the corpus directly and
  never touches BM25/dense/index code. An eval set built by eyeballing search
  results is circular and worthless.
- **State scope and limitations up front**, not buried at the end.
- **CI gates on a real regression**, not a vibe: `make eval-gate` compares
  pooled hybrid Recall@10 against `config/eval/baseline_metrics.json`.

## Data specifics (don't relitigate these)

- `corpus_roots` in `config.py` point at `edwardcrook/crypto-cointegration-signal`
  and `edwardcrook/pm-bayes-pricer` — the *published* repo, not the outer
  portfolio folder's working copies — so the index always reflects what a
  reviewer actually sees on GitHub.
- `chunk_id` is `f"{repo}/{rel_path}::{idx}[::{heading}]"`. The repo prefix is
  load-bearing: without it, two different projects' same-named files (e.g.
  both have a `README.md`) can collide on id and silently corrupt citations
  and gold-set joins. This already happened once — don't drop the prefix.
- BM25 uses the **ATIRE IDF variant** (`ln(1 + (N-n+0.5)/(n+0.5))`), not the
  original Robertson-Walker formula, specifically because the original goes
  negative for terms in more than half the corpus. Don't "simplify" this back.
- The dense leg is **TF-IDF + truncated SVD (LSA)**, not a neural embedding
  model — a deliberate choice for transparency and offline reproducibility at
  this corpus size (see README "Design decisions"), not an oversight to fix.

## Architecture decisions already made (implement, don't redesign)

1. Chunk = one markdown section or one notebook cell (`src/tradingrag/ingest/chunk.py`)
2. BM25 from scratch, RRF from scratch, LSA via scikit-learn (`src/tradingrag/retrieval/`)
3. Reciprocal rank fusion (rank position, not raw score) for combining BM25 + dense
4. Content-hashed index; `Index.load` raises if the sidecar hash doesn't match the pickle
5. Two-tier gold eval (`config/eval/analyst_gold.json` hand-labeled, `heading_gold.json`
   bootstrapped), pooled + per-tier metrics with bootstrap CIs (`src/tradingrag/eval/`)

## Checking the pipeline

1. `make index` — rebuild from the corpus, confirm chunk count and hash print sanely
2. `src/tradingrag/eval/find_chunk.py` — spot check a few `analyst_gold.json` labels
   still resolve to the chunk ids recorded there (corpus drift would break this)
3. `make eval` — confirm the BM25 > hybrid > dense ordering and CI widths look like
   the committed README table, not a fluke of one run
4. `make serve` + a manual `/search` query — confirm citations are real and specific

## Explicit non-goals

- Don't add a vector-DB framework (FAISS/Chroma/etc.) at this corpus size — brute
  force cosine over a few hundred chunks is simpler and exactly as fast in practice.
- Don't re-tune hyperparameters until hybrid beats BM25 and call it done — the
  honest finding that it doesn't, on this corpus, is the more valuable result.
- Don't add a Docker/Grafana stack before the retrieval quality story is solid;
  observability is `/metrics` (Prometheus) for now, upgraded later if justified.

## Final review gate (skills-based audit)

Once the pipeline runs end to end and the README reflects real eval numbers, run
the `project-audit` skill (`.claude/skills/project-audit/`) before calling this
done — same dispatch-and-synthesize pattern as `crypto-cointegration-signal`,
with checkers tailored to *this* project's failure modes:
`retrieval-validity-checker`, `production-robustness-checker`,
`citation-provenance-checker`, and the shared `narrative-checker`.
